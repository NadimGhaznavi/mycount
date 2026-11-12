"""Exercise the new management UI with local data and browser networking disabled."""

from datetime import datetime
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from mycount.server.ControlPages import ControlPages


CHROME = shutil.which('google-chrome') or shutil.which('chromium')


@unittest.skipUnless(CHROME, 'Chrome is required for IsoForest UI checks')
class IsoForestBrowserTests(unittest.TestCase):
    def test_schedule_queue_failure_feedback_and_local_timestamps(self):
        selected = dict(run_id=1, status='complete', feature_version='network-rotation-v2',
                        ipv4_prefix=16, ipv6_prefix=48, window_hours=24, source_views=3211,
                        observation_count=1999, anomaly_views=1396, anomaly_observations=100,
                        started_at=datetime(2026, 11, 1, 6, 30, 0, 123456),
                        completed_at=datetime(2026, 11, 1, 6, 30, 2),
                        elapsed_seconds=2, error=None, manifest=None)
        template = ControlPages().isoforest(dict(selected=selected, runs=[selected],
            observations=[], first_visit_at=None)).decode()
        for mode in ('success', 'load-error', 'save-error', 'timeout', 'queue-error'):
            with self.subTest(mode=mode), TemporaryDirectory(prefix='mycount-isoforest-browser-') as directory:
                stub = '''<script>
                const calls=[], mode=MODE;
                let settings={enabled:true,expression:'0 * * * *'};
                window.fetch=async(path,options={})=>{
                  calls.push({path,method:options.method||'GET',body:options.body});
                  if(mode==='load-error')return {ok:false,json:async()=>({error:'Settings unavailable.'})};
                  if(options.method==='POST'&&path.endsWith('-schedule')&&mode==='timeout')throw new DOMException('timeout','TimeoutError');
                  if(options.method==='POST'&&path.endsWith('-schedule')&&mode==='save-error')return {ok:false,json:async()=>({error:'Use five cron fields.'})};
                  if(path.endsWith('-run')&&mode==='queue-error')return {ok:false,json:async()=>({error:'Run could not be queued.'})};
                  if(options.body&&path.endsWith('-schedule'))settings=JSON.parse(options.body);
                  return {ok:true,json:async()=>({schedule:settings,queued:path.endsWith('-run')})};
                };</script>'''.replace('MODE', json.dumps(mode))
                harness = '''<pre id="browser-result" hidden></pre><script>
                setTimeout(async()=>{
                  const form=document.getElementById('isoforest-schedule-form'),expression=document.getElementById('isoforest-expression'),enabled=document.getElementById('isoforest-enabled');
                  const initial={expression:expression.value,enabled:enabled.checked,disabled:expression.disabled};
                  let saveStatus='';
                  if(!expression.disabled){
                    enabled.checked=false;expression.value='*/15 * * * *';
                    form.dispatchEvent(new Event('submit',{cancelable:true}));
                    await new Promise(resolve=>setTimeout(resolve,25));
                    saveStatus=document.getElementById('isoforest-schedule-status').textContent;
                    document.getElementById('isoforest-request').click();
                    await new Promise(resolve=>setTimeout(resolve,25));
                  }
                  document.getElementById('browser-result').textContent=JSON.stringify({initial,calls,saveStatus,
                    disabled:expression.disabled,scheduleStatus:document.getElementById('isoforest-schedule-status').textContent,
                    runStatus:document.getElementById('isoforest-run-status').textContent,
                    timestamps:[...document.querySelectorAll('time[data-local-time="datetime"]')].map(t=>t.textContent),
                    timezone:Intl.DateTimeFormat().resolvedOptions().timeZone});
                },100);</script>'''
                source = template.replace('<head>', '<head>'+stub).replace('</body>', harness+'</body>')
                path = Path(directory)/'page.html'
                path.write_text(source)
                result = subprocess.run([CHROME,'--headless','--no-sandbox','--disable-gpu',
                    '--disable-dev-shm-usage','--disable-background-networking','--no-first-run',
                    '--no-default-browser-check','--proxy-server=socks5://127.0.0.1:9',
                    '--proxy-bypass-list=<-loopback>','--host-resolver-rules=MAP * ~NOTFOUND',
                    f'--user-data-dir={directory}/profile','--virtual-time-budget=1500',
                    '--dump-dom',path.as_uri()],capture_output=True,text=True,check=True,timeout=30,
                    env={**os.environ,'TZ':'America/Toronto'})
                match=re.search(r'<pre id="browser-result" hidden="">(.*?)</pre>',result.stdout,re.DOTALL)
                self.assertIsNotNone(match,result.stderr)
                captured=json.loads(html.unescape(match[1]))
                self.assertEqual(captured['timezone'],'America/Toronto')
                self.assertIn('2026-11-01 01:30:00',captured['timestamps'])
                self.assertTrue(all(re.fullmatch(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d',t) for t in captured['timestamps']))
                self.assertEqual(captured['calls'][0]['path'],'/api/isoforest-schedule')
                if mode=='load-error':
                    self.assertTrue(captured['disabled'])
                    self.assertIn('Settings unavailable.',captured['scheduleStatus'])
                    self.assertEqual(len(captured['calls']),1)
                    continue
                self.assertEqual(captured['initial'],dict(expression='0 * * * *',enabled=True,disabled=False))
                self.assertFalse(captured['disabled'])
                self.assertEqual(json.loads(captured['calls'][1]['body']),dict(enabled=False,expression='*/15 * * * *'))
                self.assertEqual(captured['calls'][2]['path'],'/api/isoforest-run')
                if mode=='save-error':
                    self.assertIn('Use five cron fields.',captured['saveStatus'])
                elif mode=='timeout':
                    self.assertIn('Save could not be confirmed.',captured['saveStatus'])
                else:
                    self.assertIn('Schedule saved.',captured['saveStatus'])
                if mode=='queue-error':
                    self.assertIn('Run could not be queued.',captured['runStatus'])
                else:
                    self.assertIn('Run queued.',captured['runStatus'])
