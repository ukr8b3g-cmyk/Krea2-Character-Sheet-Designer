import unittest
from tools.validate_workflows import run

class WorkflowContracts(unittest.TestCase):
    def test_both_graphs(self):
        self.assertEqual([r['status'] for r in run()],['static_pass','static_pass'])

if __name__=='__main__':unittest.main()
