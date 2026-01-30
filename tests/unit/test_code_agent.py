import unittest
import sys
from unittest.mock import MagicMock, patch

# Mock git module before importing CodeAgentService
mock_git_mod = MagicMock()
sys.modules['git'] = mock_git_mod
sys.modules['git.exc'] = MagicMock()

from coding_agents.services.code_agent import CodeAgentService
from coding_agents.domain.models import AgentExecutionResult, IssueContext, CodeChange

class TestCodeAgentService(unittest.TestCase):
    def setUp(self):
        self.mock_github = MagicMock()
        self.mock_llm = MagicMock()
        self.mock_git = MagicMock()
        self.service = CodeAgentService(
            github_client=self.mock_github,
            llm_client=self.mock_llm,
            git_operations=self.mock_git
        )

    @patch('coding_agents.services.code_agent.os.path.exists')
    @patch('coding_agents.services.code_agent.os.makedirs')
    @patch('coding_agents.services.code_agent.settings')
    @patch('coding_agents.services.code_agent.GitOperations')
    def test_execute_success(self, mock_git_class, mock_settings, mock_makedirs, mock_exists):
        # Setup mocks
        mock_settings.get_github_token.return_value = "token"
        
        mock_issue = MagicMock(spec=IssueContext)
        mock_issue.title = "Fix bug"
        mock_issue.body = "Bug description"
        self.mock_github.get_issue.return_value = mock_issue
        self.mock_github.get_repository_tree.return_value = "tree"
        self.mock_github.get_repository_files.return_value = []
        
        self.mock_llm.generate_structured.return_value = {
            "plan": "Test plan",
            "changes": [
                {
                    "file_path": "test.py",
                    "operation": "create",
                    "content": "print('hello world, this is a long enough content')" # > 10 chars
                }
            ],
            "commit_message": "Fix: test"
        }
        
        self.mock_git.get_default_branch.return_value = "main"
        self.mock_github.get_pr_by_branch.return_value = None
        self.mock_github.create_pr.return_value = 123

        # Execute
        result = self.service.execute(
            repo="owner/repo",
            issue_number=1,
            iteration_number=1
        )

        # Assert
        self.assertTrue(result.success)
        self.assertEqual(result.pr_number, 123)

    def test_validation_rejects_empty_content(self):
        # Setup
        mock_issue = MagicMock(spec=IssueContext)
        mock_issue.title = "Test"
        mock_issue.body = "Test"
        self.mock_github.get_issue.return_value = mock_issue
        self.mock_github.get_repository_tree.return_value = "tree"
        self.mock_github.get_repository_files.return_value = []
        
        self.mock_llm.generate_structured.return_value = {
            "plan": "Test plan",
            "changes": [
                {
                    "file_path": "test.py",
                    "operation": "create",
                    "content": "short" # < 10 chars
                }
            ],
            "commit_message": "Fix: test"
        }

        # Execute
        result = self.service.execute(
            repo="owner/repo",
            issue_number=1
        )

        # Assert
        self.assertFalse(result.success)
        self.assertIn("LLM не вернул валидных изменений", result.message)

if __name__ == '__main__':
    unittest.main()
