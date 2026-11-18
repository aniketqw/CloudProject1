import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from deploy.capture_scaling import main,parse_summary

class ScalingCapture(unittest.TestCase):
    def test_accepts_exported_and_legacy_summary_without_accepting_extra_payload(self):
        for suffix in ("", "\n", r"\n", r"\\n"):
            self.assertEqual(parse_summary('{"metrics":{}}'+suffix), {"metrics":{}})
        with self.assertRaises(ValueError):parse_summary('{"metrics":{}} {"result":"PASS"}')
    def capture(self,succeeded,minimum):
        sample=0
        def run(args,**kwargs):
            nonlocal sample
            if 'logs' in args:
                return SimpleNamespace(returncode=0,stdout='K6_SUMMARY '+json.dumps({'metrics':{'http_req_duration':{'min':minimum}}})+r"\\n")
            if 'hpa' in args:
                sample+=1
                value={'items':[{'metadata':{'name':name},'spec':{'metrics':[{'resource':{'name':v}} for v in ('cpu','memory')]},'status':{'currentReplicas':sample,'desiredReplicas':sample}} for name in ('customer-service','order-service')]}
            else:value={'status':({'succeeded':1} if succeeded else {'failed':1}) if sample>=2 else {}}
            return SimpleNamespace(returncode=0,stdout=json.dumps(value))
        with tempfile.TemporaryDirectory() as d, patch('deploy.capture_scaling.ROOT',Path(d)),patch('deploy.capture_scaling.subprocess.run',side_effect=run),patch('deploy.capture_scaling.time.sleep'),patch('sys.argv',['capture','--kubeconfig','synthetic','--context','synthetic','--job','synthetic']):
            if succeeded and minimum>=0:main()
            else:
                with self.assertRaises(SystemExit):main()
            report=json.loads((Path(d)/'.local-build/evidence/scaling-local.json').read_text());samples=json.loads((Path(d)/'.local-build/evidence/scaling-local-samples.json').read_text())
            self.assertEqual(report['job'],'synthetic');self.assertEqual(len(samples['samples']),2);self.assertTrue(report['both_scaled_out'])
            return report
    def test_failed_job_is_retained_as_failed_despite_scaleout(self):
        self.assertEqual(self.capture(False,1)['result'],'FAIL')
    def test_success_requires_completed_job_and_valid_latency(self):
        self.assertEqual(self.capture(True,1)['result'],'PASS')
        self.assertEqual(self.capture(True,-1)['result'],'FAIL')
