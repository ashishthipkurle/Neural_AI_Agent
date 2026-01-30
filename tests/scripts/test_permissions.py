
import unittest
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.security.permissions import PermissionManager

class TestPermissions(unittest.TestCase):
    def test_cross_drive(self):
        pm = PermissionManager()
        # Mock allowed paths
        pm.allowed_paths = ["D:\\All Projects"]
        
        # Test path on different drive
        print("Testing C: drive path against D: allow list...")
        try:
            result = pm.is_path_allowed("C:\\Users\\test.txt")
            print(f"Result: {result}")
            self.assertFalse(result)
        except ValueError as e:
            self.fail(f"is_path_allowed raised ValueError: {e}")

if __name__ == '__main__':
    unittest.main()
