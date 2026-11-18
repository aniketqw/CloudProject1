import ast,builtins,json,unittest
from pathlib import Path
from unittest.mock import patch
from local import healthcheck
ROOT=Path(__file__).resolve().parents[1]
PRODUCERS={"notification-worker":"notification_service/worker.py","notification-consumer":"notification_service/consumer.py","notification-reconcile":"notification_service/reconcile.py","kitchen-stage-worker":"kitchen_workflow/worker.py","kitchen-sync":"kitchen_workflow/sync.py","delivery-worker":"delivery_assignment_service/worker.py","payment-worker":"payment_service/worker.py"}
class LightweightReadiness(unittest.TestCase):
    def run_probe(self,service,value):
        original=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name.split('.')[0] in {'notification_service','kitchen_workflow','delivery_assignment_service','payment_service'}:
                raise AssertionError('A heartbeat probe must not import a backend application.')
            return original(name,*args,**kwargs)
        with patch('sys.argv',['healthcheck',service]),patch('time.time',return_value=100),patch.object(Path,'read_text',return_value=json.dumps(value)),patch('builtins.__import__',side_effect=guarded):
            healthcheck.main()
    def test_fresh_connected_heartbeats_need_no_application_import(self):
        for service in PRODUCERS:
            with self.subTest(service=service):self.run_probe(service,{'at':100,'connected':True,'running':True})
    def test_stale_or_disconnected_heartbeats_are_still_rejected(self):
        for service in PRODUCERS:
            limit=10 if service=='payment-worker' else 15
            for value in ({'at':100-limit-1,'connected':True,'running':True},{'at':100,'connected':False,'running':False}):
                with self.subTest(service=service,value=value),self.assertRaises(RuntimeError):self.run_probe(service,value)
    def test_probe_paths_match_the_actual_producer_contract(self):
        for service,file in PRODUCERS.items():
            tree=ast.parse((ROOT/file).read_text(encoding='utf-8'))
            values=[n.value.args[0].value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='HEARTBEAT' for t in n.targets) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='Path']
            self.assertEqual(values,[healthcheck.HEARTBEAT_FILES[service].as_posix()])
