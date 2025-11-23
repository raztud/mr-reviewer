"""GitLab API client wrapper."""
import gitlab
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class GitLabClient:
    """Wrapper around python-gitlab for easier API access."""
    
    def __init__(self, url: str, token: str):
        """Initialize GitLab client.
        
        Args:
            url: GitLab instance URL
            token: Personal access token
        """
        self.gl = gitlab.Gitlab(url, private_token=token)
        self.gl.auth()
    
    def get_merge_request(self, project_id: str, mr_iid: int) -> Dict[str, Any]:
        """Get merge request details.
        
        Args:
            project_id: Project ID or path
            mr_iid: Merge request IID
            
        Returns:
            Dictionary with MR metadata
        """
        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            
            return {
                "iid": mr.iid,
                "title": mr.title,
                "description": mr.description or "",
                "author": mr.author.get("name", "Unknown"),
                "state": mr.state,
                "source_branch": mr.source_branch,
                "target_branch": mr.target_branch,
                "web_url": mr.web_url,
                "created_at": mr.created_at,
                "updated_at": mr.updated_at,
            }
        except Exception as e:
            logger.error(f"Error fetching MR: {e}")
            raise
    
    def get_merge_request_changes(self, project_id: str, mr_iid: int) -> Dict[str, Any]:
        """Get merge request changes (diffs).
        
        Args:
            project_id: Project ID or path
            mr_iid: Merge request IID
            
        Returns:
            Dictionary with changes information
        """
        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            changes = mr.changes()
            
            return {
                "changes": changes.get("changes", []),
                "diff_stats": {
                    "additions": sum(c.get("diff", "").count("\n+") for c in changes.get("changes", [])),
                    "deletions": sum(c.get("diff", "").count("\n-") for c in changes.get("changes", [])),
                    "files_changed": len(changes.get("changes", [])),
                }
            }
        except Exception as e:
            logger.error(f"Error fetching MR changes: {e}")
            raise
    
    def get_merge_request_discussions(self, project_id: str, mr_iid: int) -> List[Dict[str, Any]]:
        """Get merge request discussions/comments.
        
        Args:
            project_id: Project ID or path
            mr_iid: Merge request IID
            
        Returns:
            List of discussion threads
        """
        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            discussions = mr.discussions.list(get_all=True)
            
            result = []
            for discussion in discussions:
                notes = []
                for note in discussion.attributes.get("notes", []):
                    notes.append({
                        "author": note.get("author", {}).get("name", "Unknown"),
                        "body": note.get("body", ""),
                        "created_at": note.get("created_at", ""),
                    })
                
                result.append({
                    "id": discussion.id,
                    "notes": notes,
                })
            
            return result
        except Exception as e:
            logger.error(f"Error fetching MR discussions: {e}")
            raise
    
    def post_merge_request_note(self, project_id: str, mr_iid: int, body: str) -> Dict[str, Any]:
        """Post a note/comment to a merge request.
        
        Args:
            project_id: Project ID or path
            mr_iid: Merge request IID
            body: Comment text
            
        Returns:
            Dictionary with created note information
        """
        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            note = mr.notes.create({"body": body})
            
            return {
                "id": note.id,
                "body": note.body,
                "created_at": note.created_at,
                "web_url": f"{mr.web_url}#note_{note.id}",
            }
        except Exception as e:
            logger.error(f"Error posting MR note: {e}")
            raise
    
    @staticmethod
    def parse_mr_url(url: str) -> Optional[tuple[str, int]]:
        """Parse GitLab MR URL to extract project and MR IID.
        
        Args:
            url: GitLab MR URL
            
        Returns:
            Tuple of (project_id, mr_iid) or None if parsing fails
            
        Examples:
            https://gitlab.com/group/project/-/merge_requests/123
            -> ("group/project", 123)
        """
        try:
            # Handle URLs like: https://gitlab.com/group/project/-/merge_requests/123
            parts = url.split("/-/merge_requests/")
            if len(parts) != 2:
                return None
            
            # Extract project path (everything after the domain)
            project_part = parts[0].split("/", 3)
            if len(project_part) < 4:
                return None
            
            project_id = project_part[3]
            
            # Extract MR IID
            mr_iid = int(parts[1].split("/")[0].split("?")[0].split("#")[0])
            
            return (project_id, mr_iid)
        except Exception as e:
            logger.error(f"Error parsing MR URL {url}: {e}")
            return None

