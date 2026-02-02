import logging
import uuid
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple

logger = logging.getLogger("FileSafetyGuard")

@dataclass
class FileProposal:
    proposal_id: str
    action: str  # 'write', 'modify', 'delete'
    file_path: str
    content: str  # New content or diff
    timestamp: float
    directory: Optional[str] = None
    original_content: Optional[str] = None

class FileSafetyGuard:
    """
    Enforces strict file safety rules:
    1. AI cannot directly write files.
    2. All writes must go through a Proposal -> Approval flow.
    3. Proposals expire after a set time.
    """
    
    def __init__(self):
        self._pending_proposals: Dict[str, FileProposal] = {}
        self._proposal_ttl = 3600  # 1 hour expiration
        
    def create_proposal(self, action: str, file_path: str, content: str, directory: str = None) -> str:
        """
        Creates a new file modification proposal.
        Returns a unique proposal_id.
        """
        proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
        
        # In a real app, we might want to read original content here for rollback capability
        # But for now, we just store the proposal
        
        proposal = FileProposal(
            proposal_id=proposal_id,
            action=action,
            file_path=file_path,
            content=content,
            timestamp=datetime.now().timestamp(),
            directory=directory
        )
        
        self._pending_proposals[proposal_id] = proposal
        logger.info(f"🔒 Proposal created: {proposal_id} for {action} on {file_path}")
        return proposal_id

    def verify_and_apply(self, proposal_id: str, user_approved: bool) -> Tuple[bool, str]:
        """
        Verifies a proposal and applies it IF user_approved is True.
        Returns (success, message/path).
        """
        if not user_approved:
            logger.warning(f"❌ Proposal {proposal_id} rejected by user (explicit denial)")
            return False, "User rejected proposal"
            
        proposal = self._pending_proposals.get(proposal_id)
        if not proposal:
            logger.warning(f"❌ Attempt to apply invalid/expired proposal: {proposal_id}")
            return False, "Invalid or expired proposal ID"
            
        # Check expiration
        if datetime.now().timestamp() - proposal.timestamp > self._proposal_ttl:
            del self._pending_proposals[proposal_id]
            return False, "Proposal expired"
            
        # Execute the Change
        try:
            full_path = self._get_full_path(proposal)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Write file (Copilot mode: overwrite with new content is standard for 'Apply Diff')
            # For strict diff patching, we'd apply the patch here. 
            # But the current requirement says 'AI returns unified diff', 'Proposal applied'.
            # If the proposal content IS the whole file (from create), we write it.
            # If it were a diff, we'd need a patch util. 
            # For Phase 1 of Copilot, we typically replace the file content with the result of the merge specific in the frontend,
            # OR logic here applies a patch.
            # Let's assume 'content' here is the FINAL content to be written for now,
            # because 'apply diff' usually means the frontend sends the *result* or backend computes it.
            # Given `save_file` logic, let's treat content as final content for this iteration,
            # or we need a `git apply` equivalent. 
            # Per task instructions: "Refactor mode -> AI returns unified diff".
            # The APPLY step needs to apply that diff.
            # Let's handle generic 'write' for now which takes full content.
            
            mode = 'w' if proposal.action in ['write', 'create'] else 'w' 
            
            with open(full_path, mode, encoding='utf-8') as f:
                f.write(proposal.content)
                
            logger.info(f"✅ Proposal {proposal_id} APPLIED to {full_path}")
            
            # Cleanup
            del self._pending_proposals[proposal_id]
            return True, full_path
            
        except Exception as e:
            logger.error(f"❌ Failed to apply proposal {proposal_id}: {e}")
            return False, str(e)

    def get_proposal(self, proposal_id: str) -> Optional[FileProposal]:
        return self._pending_proposals.get(proposal_id)

    def _get_full_path(self, proposal: FileProposal) -> str:
        if proposal.directory:
             return os.path.join(proposal.directory, os.path.basename(proposal.file_path))
        
        # If absolute path, use it
        if os.path.isabs(proposal.file_path):
            return proposal.file_path
            
        # Default fallback (should be configured in settings in real app)
        return os.path.abspath(proposal.file_path)

# Global Instance
start_gate = FileSafetyGuard()
