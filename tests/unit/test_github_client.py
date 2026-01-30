import unittest
from unittest.mock import MagicMock, patch
from coding_agents.infrastructure.github_client import GitHubClient
from coding_agents.domain.models import IssueContext, PRContext

class TestGitHubClient(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('coding_agents.infrastructure.github_client.Github')
        self.mock_github_class = self.patcher.start()
        self.mock_github_instance = self.mock_github_class.return_value
        self.client = GitHubClient(token="fake-token")

    def tearDown(self):
        self.patcher.stop()

    def test_get_issue_success(self):
        # Setup
        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_issue.number = 1
        mock_issue.title = "Test Issue"
        mock_issue.body = "Test Body"
        mock_issue.labels = [MagicMock(name="bug")]
        mock_issue.labels[0].name = "bug"
        
        self.mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue

        # Execute
        result = self.client.get_issue("owner/repo", 1)

        # Assert
        self.assertIsInstance(result, IssueContext)
        self.assertEqual(result.number, 1)
        self.assertEqual(result.title, "Test Issue")
        self.mock_github_instance.get_repo.assert_called_with("owner/repo")
        mock_repo.get_issue.assert_called_with(1)

    def test_get_pr_by_branch_found(self):
        # Setup
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.number = 5
        mock_pr.head.ref = "feature-branch"
        mock_pr.head.sha = "sha123"
        mock_pr.title = "PR Title"
        mock_pr.body = "PR Body"
        mock_pr.base.ref = "main"
        mock_pr.state = "open"
        mock_pr.get_files.return_value = []
        
        self.mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.owner.login = "owner"
        mock_repo.get_pulls.return_value = [mock_pr]

        # Execute
        result = self.client.get_pr_by_branch("owner/repo", "feature-branch")

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.number, 5)
        mock_repo.get_pulls.assert_called_with(head="owner:feature-branch", state="open")

    def test_get_pr_by_branch_not_found(self):
        # Setup
        mock_repo = MagicMock()
        self.mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.owner.login = "owner"
        mock_repo.get_pulls.return_value = []

        # Execute
        result = self.client.get_pr_by_branch("owner/repo", "non-existent")

        # Assert
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
