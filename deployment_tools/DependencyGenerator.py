"""Generate a static dependency map from scans and project-supplied rules."""

import ast
import json
from pathlib import Path, PurePosixPath
import re


class DependencyGenerator:
    def __init__(self, root: Path, rules_file: str) -> None:
        self.root = root
        self.rules_file = self._path(rules_file)
        self.rules = json.loads((root / rules_file).read_text())
        if not isinstance(self.rules, dict):
            raise ValueError('Dependency rules must be an object')
        for key in ('output', 'template', 'python_roots', 'template_roots', 'scan', 'exclude', 'targets', 'extra'):
            if key not in self.rules:
                raise ValueError(f'Missing dependency rule: {key}')
        for key in ('output', 'template'):
            if not isinstance(self.rules[key], str):
                raise ValueError(f'{key} must be a repository-relative path')
            self._path(self.rules[key])
        for key in ('python_roots', 'template_roots', 'scan', 'exclude'):
            if not isinstance(self.rules[key], list) or any(not isinstance(value, str) for value in self.rules[key]):
                raise ValueError(f'{key} must be a list of strings')
        for key in ('targets', 'extra'):
            values = self.rules[key]
            if not isinstance(values, dict) or any(
                    not isinstance(children, list) or any(not isinstance(child, str) for child in children)
                    for children in values.values()):
                raise ValueError(f'{key} must map names to lists of paths')

    @staticmethod
    def _path(name: str) -> str:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or path.as_posix() != name or name == '.':
            raise ValueError(f'Use a repository-relative path: {name}')
        return name

    def build(self) -> dict[str, tuple[str, ...]]:
        rules = self.rules
        names = {self._path(path.relative_to(self.root).as_posix())
                 for pattern in rules['scan'] for path in self.root.glob(pattern)
                 if path.is_file() and '__pycache__' not in path.parts}
        names -= set(rules['exclude'])
        names.update((self.rules_file, rules['template'], rules['output']))
        names.update(rules['extra'])
        for children in (*rules['targets'].values(), *rules['extra'].values()):
            names.update(children)
        for name in names:
            self._path(name)
            if name != rules['output'] and not (self.root / name).is_file():
                raise ValueError(f'Dependency file is missing: {name}')
        graph = {name: set(rules['extra'].get(name, ())) for name in names}
        modules = {name.removesuffix('.py').replace('/', '.').removesuffix('.__init__'): name
                   for name in names if name.endswith('.py')}
        for name in sorted(names):
            if not name.endswith(('.py', '.sh', '.html')):
                continue
            source = (self.root / name).read_text() if name != rules['output'] else (
                (self.root / rules['template']).read_text().replace('{{TARGETS}}', '{}').replace('{{DEPENDENCIES}}', '{}'))
            if name.endswith('.py'):
                self._python(name, source, graph[name], modules)
                for parent in PurePosixPath(name).parents:
                    initializer = str(parent / '__init__.py')
                    if initializer in names and initializer != name:
                        graph[name].add(initializer)
            elif name.endswith('.sh'):
                # Python heredocs are scanned as code; shell calls use explicit rules.
                for marker, block in re.findall(r"<<'(PY\w*)'\n(.*?)\n\1(?:\n|$)", source, re.S):
                    self._python(name, block, graph[name], modules)
            elif name.endswith('.html'):
                source = re.sub(r'{#.*?#}', '', source, flags=re.S)
                for command, expression in re.findall(r'{%[-+]?\s*(extends|include|import|from)\s+(.*?)\s*[-+]?%}', source, re.S):
                    literal = re.match(r'''(['"])(.*?)\1''', expression)
                    suffix = expression[literal.end():].strip() if literal else ''
                    static_suffix = (not suffix or command == 'include' and suffix in (
                        'ignore missing', 'with context', 'without context',
                        'ignore missing with context', 'ignore missing without context')
                        or command == 'import' and suffix.startswith('as ')
                        or command == 'from' and suffix.startswith('import '))
                    if literal is None or not static_suffix:
                        if name not in rules['extra']:
                            raise ValueError(f'Declare dynamic template dependencies in extra: {name}')
                        continue
                    roots = [folder for folder in rules['template_roots'] if name.startswith(folder + '/')]
                    if len(roots) != 1:
                        raise ValueError(f'Assign one template root to {name}')
                    graph[name].add(str(PurePosixPath(roots[0]) / literal.group(2)))
        for name, children in graph.items():
            for child in children:
                self._path(child)
                if child not in graph:
                    raise ValueError(f'{name}: dependency is not scanned or declared: {child}')
        visited, active = set(), []

        def visit(name):
            if name in active:
                raise ValueError('Dependency cycle: ' + ' -> '.join((*active, name)))
            if name in visited:
                return
            active.append(name)
            for child in sorted(graph[name]):
                visit(child)
            active.pop()
            visited.add(name)

        for children in rules['targets'].values():
            for name in children:
                visit(name)
        unowned = set(graph) - visited
        if unowned:
            raise ValueError('Assign unreachable artifacts to a target or parent: ' + ', '.join(sorted(unowned)))
        return {name: tuple(sorted(children)) for name, children in sorted(graph.items())}

    def _python(self, name: str, source: str, children: set[str], modules: dict[str, str]) -> None:
        def resolve(module):
            if module.split('.')[0] not in self.rules['python_roots']:
                return
            if module not in modules:
                raise ValueError(f'{name}: unresolved local import: {module}')
            children.add(modules[module])

        for node in ast.walk(ast.parse(source, filename=name)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolve(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                if node.level:
                    package = name.removesuffix('.py').split('/')[:-1]
                    if node.level > len(package):
                        raise ValueError(f'{name}: relative import escapes its package')
                    module = '.'.join(package[:len(package) - node.level + 1] + ([module] if module else []))
                resolve(module)
                for alias in node.names:
                    child = module + '.' + alias.name
                    if child in modules:
                        children.add(modules[child])
            elif isinstance(node, ast.Call) and (
                    isinstance(node.func, ast.Name) and node.func.id in ('__import__', 'import_module')
                    or isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module'):
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    resolve(node.args[0].value)
                elif name not in self.rules['extra']:
                    raise ValueError(f'Declare dynamic import dependencies in extra: {name}')

    def render(self) -> str:
        graph = self.build()

        def mapping(values):
            lines = ['{']
            for name, children in sorted(values.items()):
                lines.append(f'        {json.dumps(name)}: (')
                lines.extend(f'            {json.dumps(child)},' for child in sorted(children))
                lines.append('        ),')
            lines.append('    }')
            return '\n'.join(lines)

        template = (self.root / self.rules['template']).read_text()
        if template.count('{{TARGETS}}') != 1 or template.count('{{DEPENDENCIES}}') != 1:
            raise ValueError('Output template must contain TARGETS and DEPENDENCIES placeholders once each')
        return template.replace(
            '{{TARGETS}}', mapping(self.rules['targets'])).replace('{{DEPENDENCIES}}', mapping(graph))

    def update(self, *, check: bool = False) -> bool:
        rendered = self.render()
        path = self.root / self.rules['output']
        matches = path.exists() and path.read_text() == rendered
        if not check and not matches:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(rendered)
            temporary.replace(path)
        return matches if check else True
