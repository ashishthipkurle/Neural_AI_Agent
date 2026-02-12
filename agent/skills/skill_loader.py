"""
Skill Loader - Dynamic skill discovery and lifecycle management.

This module is responsible for:
- Discovering skills in the agent/skills/ directory
- Loading/unloading skills with proper lifecycle hooks
- Providing skill registry for the router
"""

import os
import importlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type, Any

from .base_skill import BaseSkill, SkillHealth, SkillManifest


class SkillLoader:
    """
    Manages skill discovery, loading, and lifecycle.
    
    Skills are discovered from:
    1. Built-in skills in agent/skills/*/
    2. (Future) Plugin skills from agent/plugins/
    """
    
    def __init__(self, skills_dir: Optional[Path] = None, injectables: Dict[str, Any] = None):
        self.logger = logging.getLogger("SkillLoader")
        self.injectables = injectables or {}
        
        # Default to agent/skills/
        if skills_dir is None:
            skills_dir = Path(__file__).parent
        self.skills_dir = skills_dir
        
        # Loaded skill instances
        self._skills: Dict[str, BaseSkill] = {}
        
        # Skill classes discovered but not loaded
        self._discovered: Dict[str, Type[BaseSkill]] = {}
        
        self.logger.info(f"SkillLoader initialized. Skills dir: {self.skills_dir}")
    
    def discover(self) -> List[str]:
        """
        Discover all available skills in the skills directory.
        
        Looks for:
        - agent/skills/{skill_name}/skill.py with a class inheriting BaseSkill
        - agent/skills/{skill_name}_skill.py (flat structure)
        
        Returns:
            List of discovered skill names.
        """
        discovered = []
        
        # Scan for skill subdirectories
        for item in self.skills_dir.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                skill_file = item / "skill.py"
                if skill_file.exists():
                    skill_class = self._load_skill_class(item.name, skill_file)
                    if skill_class:
                        self._discovered[item.name] = skill_class
                        discovered.append(item.name)
            
            # Also check for {name}_skill.py files
            elif item.is_file() and item.name.endswith('_skill.py'):
                skill_name = item.name.replace('_skill.py', '')
                skill_class = self._load_skill_class(skill_name, item)
                if skill_class:
                    self._discovered[skill_name] = skill_class
                    discovered.append(skill_name)
        
        self.logger.info(f"Discovered {len(discovered)} skills: {discovered}")
        return discovered
    
    def _load_skill_class(self, skill_name: str, skill_file: Path) -> Optional[Type[BaseSkill]]:
        """Load a skill class from file."""
        try:
            # Convert path to module name
            # agent/skills/browser/skill.py -> agent.skills.browser.skill
            rel_path = skill_file.relative_to(Path(__file__).parent.parent.parent)
            module_name = str(rel_path).replace(os.sep, '.').replace('.py', '')
            
            spec = importlib.util.spec_from_file_location(module_name, skill_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find the skill class (subclass of BaseSkill)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, BaseSkill) and 
                    attr is not BaseSkill):
                    self.logger.debug(f"Found skill class: {attr_name} in {skill_file}")
                    return attr
            
            self.logger.warning(f"No BaseSkill subclass found in {skill_file}")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to load skill from {skill_file}: {e}")
            return None
    
    def load(self, skill_name: str) -> Optional[BaseSkill]:
        """
        Load and initialize a skill by name.
        
        Calls on_load() lifecycle hook.
        """
        if skill_name in self._skills:
            self.logger.debug(f"Skill '{skill_name}' already loaded.")
            return self._skills[skill_name]
        
        if skill_name not in self._discovered:
            self.logger.error(f"Skill '{skill_name}' not discovered. Run discover() first.")
            return None
        
        try:
            skill_class = self._discovered[skill_name]
            
            # fast dependency injection
            import inspect
            sig = inspect.signature(skill_class.__init__)
            params = {}
            
            for param_name, search_param in sig.parameters.items():
                if param_name == 'self':
                    continue
                
                # Check directly in injectables
                if param_name in self.injectables:
                    params[param_name] = self.injectables[param_name]
                
                # Check by type hint if possible
                elif search_param.annotation != inspect.Parameter.empty:
                     for obj in self.injectables.values():
                         if isinstance(obj, search_param.annotation):
                             params[param_name] = obj
                             break
            
            # If config is needed but not found, inject generic empty dict to prevent failure
            if 'config' in sig.parameters and 'config' not in params:
                params['config'] = self.injectables.get('config', {})
                
            skill = skill_class(**params)
            
            # Handle both sync and async on_load
            import asyncio
            result = skill.on_load()
            if asyncio.iscoroutine(result):
                # Schedule async on_load - it will run when the event loop is available
                # Store for deferred initialization during on_start
                skill._deferred_async_load = True
                self.logger.info(f"Skill '{skill_name}' has async on_load - will initialize during start()")
            
            self._skills[skill_name] = skill
            self.logger.info(f"Loaded skill: {skill_name}")
            return skill
            
        except Exception as e:
            self.logger.error(f"Failed to load skill '{skill_name}': {e}")
            return None
    
    def load_all(self) -> Dict[str, BaseSkill]:
        """Load all discovered skills."""
        if not self._discovered:
            self.discover()
        
        for skill_name in self._discovered:
            self.load(skill_name)
        
        return self._skills
    
    def unload(self, skill_name: str) -> bool:
        """
        Unload a skill by name.
        
        Calls on_unload() lifecycle hook.
        """
        if skill_name not in self._skills:
            self.logger.warning(f"Skill '{skill_name}' not loaded.")
            return False
        
        try:
            skill = self._skills[skill_name]
            skill.on_unload()
            del self._skills[skill_name]
            self.logger.info(f"Unloaded skill: {skill_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unload skill '{skill_name}': {e}")
            return False
    
    def unload_all(self) -> None:
        """Unload all skills (cleanup on shutdown)."""
        for skill_name in list(self._skills.keys()):
            self.unload(skill_name)
    
    def get(self, skill_name: str) -> Optional[BaseSkill]:
        """Get a loaded skill by name."""
        return self._skills.get(skill_name)
    
    def get_all(self) -> Dict[str, BaseSkill]:
        """Get all loaded skills."""
        return self._skills.copy()
    
    def get_healthy_skills(self) -> Dict[str, BaseSkill]:
        """Get only skills with READY health status."""
        return {
            name: skill 
            for name, skill in self._skills.items() 
            if skill.health() == SkillHealth.READY
        }
    
    def get_skill_for_intent(self, intent: str) -> Optional[BaseSkill]:
        """
        Find the best skill to handle an intent.
        
        Returns the skill with highest confidence score.
        """
        best_skill = None
        best_confidence = 0.0
        
        for skill in self._skills.values():
            if skill.health() != SkillHealth.READY:
                continue
            
            confidence = skill.can_handle(intent)
            if confidence > best_confidence:
                best_confidence = confidence
                best_skill = skill
        
        if best_skill:
            self.logger.debug(f"Intent '{intent}' -> Skill '{best_skill.name}' (conf={best_confidence:.2f})")
        
        return best_skill
    
    def list_all_actions(self) -> Dict[str, List[str]]:
        """List all actions from all loaded skills."""
        return {
            name: skill.get_actions()
            for name, skill in self._skills.items()
        }
