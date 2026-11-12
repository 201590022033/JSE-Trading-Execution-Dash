"""Exercise the real dashboard button-status script with a minimal DOM."""
import subprocess
import unittest
from pathlib import Path


class DashboardRefreshStatusTests(unittest.TestCase):
    def test_button_reports_refresh_result_and_partial_state(self):
        script = Path(__file__).parent/'static/js/tab-data-status.js'
        js = r'''
const fs = require('fs'), vm = require('vm');
let changed;
const status = {textContent: 'Data unavailable'};
const panel = {querySelectorAll: () => [status]};
const button = {textContent:'Refresh feeds', dataset:{}, title:'',
 closest: s => s === '.tab-data-status' ? null : panel,
 addEventListener: (name, fn) => {if(name === 'click') button.click = fn}};
const document = {querySelector: () => null, getElementById: () => null,
 querySelectorAll: () => [button]};
class MutationObserver { constructor(fn){changed=fn} observe(){} }
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {document,MutationObserver,setInterval: () => 0});
if(button.dataset.refreshState !== 'unavailable') throw Error('missing red');
button.click(); if(button.dataset.refreshState !== 'checking') throw Error('missing checking');
status.textContent = 'AVAILABLE: refreshed data'; changed();
if(button.dataset.refreshState !== 'available') throw Error('missing green');
status.textContent = 'AVAILABLE; another source unavailable'; changed();
if(button.dataset.refreshState !== 'attention') throw Error('missing partial state');
'''
        result=subprocess.run(['node','-e',js,str(script)],capture_output=True,text=True,check=False)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__ == '__main__': unittest.main()
