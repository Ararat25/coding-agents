import unittest
from unittest.mock import MagicMock
from coding_agents.services.reviewer_agent import ReviewerAgentService
from coding_agents.domain.models import ReviewerContext, ReviewResult, ReviewVerdict

class TestReviewerAgentService(unittest.TestCase):
    def setUp(self):
        self.mock_github = MagicMock()
        self.mock_llm = MagicMock()
        self.service = ReviewerAgentService(
            github_client=self.mock_github,
            llm_client=self.mock_llm
        )

    def test_publish_review_always_uses_comment(self):
        # Setup
        review_result = ReviewResult(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="Needs work",
            comments=[]
        )
        
        # Execute
        self.service.publish_review(
            repo="owner/repo",
            pr_number=5,
            review_result=review_result
        )

        # Assert
        args, kwargs = self.mock_github.create_review.call_args
        self.assertEqual(kwargs['event'], "COMMENT")
        self.assertIn("Требуются изменения", kwargs['body'])

    def test_publish_review_approved_as_comment(self):
        # Setup
        review_result = ReviewResult(
            verdict=ReviewVerdict.APPROVED,
            summary="Looks good",
            comments=[]
        )
        
        # Execute
        self.service.publish_review(
            repo="owner/repo",
            pr_number=5,
            review_result=review_result
        )

        # Assert
        args, kwargs = self.mock_github.create_review.call_args
        self.assertEqual(kwargs['event'], "COMMENT")
        self.assertIn("Код готов к approve", kwargs['body'])

if __name__ == '__main__':
    unittest.main()
