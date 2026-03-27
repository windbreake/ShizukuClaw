"""
Dynamic loading module for web pages
"""
import json
from typing import Dict, Any

class DynamicLoader:
    """
    Handles dynamic loading of web page components
    """
    
    def __init__(self):
        self.components = {}
    
    def register_component(self, name: str, component: Any) -> None:
        """
        Register a component for dynamic loading
        
        Args:
            name: Component name
            component: Component to register
        """
        self.components[name] = component
    
    def load_component(self, name: str) -> Any:
        """
        Load a registered component by name
        
        Args:
            name: Component name to load
            
        Returns:
            The loaded component or None if not found
        """
        return self.components.get(name)
    
    def get_components_list(self) -> Dict[str, Any]:
        """
        Get list of all registered components
        
        Returns:
            Dictionary of all components
        """
        return self.components

# Example usage
if __name__ == "__main__":
    loader = DynamicLoader()
    print("Dynamic loader initialized")