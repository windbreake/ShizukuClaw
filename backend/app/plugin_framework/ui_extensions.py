# -*- coding: utf-8 -*-
"""Plugin UI Extension Framework.

Provides a safe way for plugins to extend the UI without modifying core code.
Uses a hook-based system with sandboxed execution.
"""

import logging
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field


logger = logging.getLogger("plugin_ui_framework")


@dataclass
class UIMenuItem:
    """Represents a menu item added by a plugin."""
    id: str  # Unique identifier
    label: str  # Display text
    icon: str = "fas fa-puzzle-piece"  # Icon class (FontAwesome)
    order: int = 100  # Sort order (lower = higher priority)
    action: Optional[str] = None  # JavaScript function to call
    url: Optional[str] = None  # URL to navigate to
    parent_id: Optional[str] = None  # Parent menu item ID (for submenus)
    requires_permission: Optional[str] = None  # Required permission
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "icon": self.icon,
            "order": self.order,
            "action": self.action,
            "url": self.url,
            "parent_id": self.parent_id,
            "requires_permission": self.requires_permission
        }


@dataclass
class UIPage:
    """Represents a page added by a plugin."""
    id: str  # Unique page ID
    title: str  # Page title
    route: str  # URL route (e.g., /plugins/my-plugin/page)
    content_type: str = "html"  # html, iframe, component
    content: Optional[str] = None  # HTML content or component name
    template_file: Optional[str] = None  # Path to template file
    requires_auth: bool = True  # Requires authentication
    permissions: List[str] = field(default_factory=list)  # Required permissions
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "route": self.route,
            "content_type": self.content_type,
            "content": None,  # Never expose HTML content in JSON - load via route on demand
            "template_file": self.template_file,
            "requires_auth": self.requires_auth,
            "permissions": self.permissions
        }


@dataclass
class UISettingSection:
    """Represents a settings section added by a plugin."""
    id: str  # Unique section ID
    title: str  # Section title
    description: str = ""  # Section description
    order: int = 100  # Display order
    fields: List[Dict] = field(default_factory=list)  # Setting fields (schema format)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "order": self.order,
            "fields": self.fields
        }


@dataclass
class UIWidget:
    """Represents a widget/dashboard element added by a plugin."""
    id: str  # Unique widget ID
    title: str  # Widget title
    widget_type: str = "card"  # card, chart, table, stats
    position: str = "dashboard"  # dashboard, sidebar, header
    order: int = 100  # Display order
    config: Dict[str, Any] = field(default_factory=dict)  # Widget configuration
    data_source: Optional[str] = None  # API endpoint for data
    refresh_interval: Optional[int] = None  # Auto-refresh interval (seconds)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "widget_type": self.widget_type,
            "position": self.position,
            "order": self.order,
            "config": self.config,
            "data_source": self.data_source,
            "refresh_interval": self.refresh_interval
        }


@dataclass
class UIModal:
    """Represents a modal dialog added by a plugin."""
    id: str  # Unique modal ID
    title: str  # Modal title
    size: str = "md"  # sm, md, lg, xl
    content_type: str = "html"  # html, form, component
    content: Optional[str] = None  # HTML content
    form_schema: Optional[Dict] = None  # Form schema (if content_type is form)
    on_submit: Optional[str] = None  # JavaScript callback on submit
    buttons: List[Dict] = field(default_factory=list)  # Custom buttons
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "size": self.size,
            "content_type": self.content_type,
            "content": self.content,
            "form_schema": self.form_schema,
            "on_submit": self.on_submit,
            "buttons": self.buttons
        }


@dataclass
class ApiRoute:
    """Represents an API endpoint registered by a plugin."""
    method: str  # HTTP method: GET, POST, PUT, DELETE
    path: str  # Route path relative to /api/plugins/<plugin_name>/
    handler: Callable  # Handler function(flask_request) -> flask_response
    plugin_name: str = ""

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "path": self.path,
            "plugin_name": self.plugin_name
        }


class PluginUIRegistry:
    """Registry for plugin UI extensions."""
    
    def __init__(self):
        self._menu_items: Dict[str, UIMenuItem] = {}
        self._pages: Dict[str, UIPage] = {}
        self._setting_sections: Dict[str, UISettingSection] = {}
        self._widgets: Dict[str, UIWidget] = {}
        self._modals: Dict[str, UIModal] = {}
        self._api_routes: Dict[str, ApiRoute] = {}
        self._custom_hooks: Dict[str, List[Callable]] = {}
        
    def register_menu_item(self, item: UIMenuItem, plugin_name: str) -> bool:
        """Register a menu item from a plugin."""
        try:
            # Validate required fields
            if not item.id or not item.label:
                logger.warning(f"Plugin {plugin_name}: Menu item missing id or label")
                return False
            
            # Check for duplicates
            if item.id in self._menu_items:
                logger.warning(f"Plugin {plugin_name}: Menu item '{item.id}' already exists")
                return False
            
            # Add plugin namespace to ID to prevent conflicts
            namespaced_id = f"{plugin_name}.{item.id}"
            item.id = namespaced_id
            
            # Update parent_id if it exists
            if item.parent_id and not item.parent_id.startswith(plugin_name):
                item.parent_id = f"{plugin_name}.{item.parent_id}"
            
            self._menu_items[namespaced_id] = item
            logger.info(f"Plugin {plugin_name}: Registered menu item '{namespaced_id}'")
            return True
        except Exception as e:
            logger.error(f"Plugin {plugin_name}: Failed to register menu item: {e}")
            return False
    
    def register_page(self, page: UIPage, plugin_name: str) -> bool:
        """Register a page from a plugin."""
        try:
            if not page.id or not page.route:
                logger.warning(f"Plugin {plugin_name}: Page missing id or route")
                return False
            
            if page.id in self._pages:
                logger.warning(f"Plugin {plugin_name}: Page '{page.id}' already exists")
                return False
            
            # Namespace the page ID and route
            namespaced_id = f"{plugin_name}.{page.id}"
            page.id = namespaced_id
            if not page.route.startswith(f"/plugins/{plugin_name}"):
                page.route = f"/plugins/{plugin_name}{page.route}"
            
            self._pages[namespaced_id] = page
            logger.info(f"Plugin {plugin_name}: Registered page '{namespaced_id}' at {page.route}")
            return True
        except Exception as e:
            logger.error(f"Plugin {plugin_name}: Failed to register page: {e}")
            return False
    
    def register_setting_section(self, section: UISettingSection, plugin_name: str) -> bool:
        """Register a settings section from a plugin."""
        try:
            if not section.id or not section.title:
                logger.warning(f"Plugin {plugin_name}: Setting section missing id or title")
                return False
            
            namespaced_id = f"{plugin_name}.{section.id}"
            section.id = namespaced_id
            
            self._setting_sections[namespaced_id] = section
            logger.info(f"Plugin {plugin_name}: Registered setting section '{namespaced_id}'")
            return True
        except Exception as e:
            logger.error(f"Plugin {plugin_name}: Failed to register setting section: {e}")
            return False
    
    def register_widget(self, widget: UIWidget, plugin_name: str) -> bool:
        """Register a widget from a plugin."""
        try:
            if not widget.id or not widget.title:
                logger.warning(f"Plugin {plugin_name}: Widget missing id or title")
                return False
            
            namespaced_id = f"{plugin_name}.{widget.id}"
            widget.id = namespaced_id
            
            self._widgets[namespaced_id] = widget
            logger.info(f"Plugin {plugin_name}: Registered widget '{namespaced_id}'")
            return True
        except Exception as e:
            logger.error(f"Plugin {plugin_name}: Failed to register widget: {e}")
            return False
    
    def register_modal(self, modal: UIModal, plugin_name: str) -> bool:
        """Register a modal from a plugin."""
        try:
            if not modal.id or not modal.title:
                logger.warning(f"Plugin {plugin_name}: Modal missing id or title")
                return False
            
            namespaced_id = f"{plugin_name}.{modal.id}"
            modal.id = namespaced_id
            
            self._modals[namespaced_id] = modal
            logger.info(f"Plugin {plugin_name}: Registered modal '{namespaced_id}'")
            return True
        except Exception as e:
            logger.error(f"Plugin {plugin_name}: Failed to register modal: {e}")
            return False
    
    def register_hook(self, hook_name: str, callback: Callable, plugin_name: str) -> bool:
        """Register a callback for a UI hook."""
        try:
            if hook_name not in self._custom_hooks:
                self._custom_hooks[hook_name] = []
            
            self._custom_hooks[hook_name].append(callback)
            logger.info(f"Plugin {plugin_name}: Registered hook '{hook_name}'")
            return True
        except Exception as e:
            logger.error(f"Plugin {plugin_name}: Failed to register hook: {e}")
            return False
    
    def register_api_route(self, route: ApiRoute, plugin_name: str) -> bool:
        """Register an API endpoint from a plugin."""
        try:
            if not route.method or not route.path:
                logger.warning(f"Plugin {plugin_name}: API route missing method or path")
                return False
            
            route.plugin_name = plugin_name
            method = route.method.upper()
            norm_path = route.path if route.path.startswith("/") else f"/{route.path}"
            # Normalize: strip /api/plugins/<plugin_name> prefix if present
            prefix = f"/api/plugins/{plugin_name}"
            if norm_path.startswith(prefix):
                norm_path = norm_path[len(prefix):]
            if not norm_path.startswith("/"):
                norm_path = f"/{norm_path}"
            
            key = f"{plugin_name}:{method}:{norm_path}"
            if key in self._api_routes:
                logger.warning(f"Plugin {plugin_name}: API route '{method} {norm_path}' already exists, overwriting")
            
            route.path = norm_path
            self._api_routes[key] = route
            logger.info(f"Plugin {plugin_name}: Registered API route {method} {norm_path}")
            return True
        except Exception as e:
            logger.error(f"Plugin {plugin_name}: Failed to register API route: {e}")
            return False
    
    def find_api_handler(self, method: str, path: str, plugin_name: str):
        """Find an API handler for the given method, path, and plugin name."""
        method = method.upper()
        if not path.startswith("/"):
            path = f"/{path}"
        key = f"{plugin_name}:{method}:{path}"
        route = self._api_routes.get(key)
        if route:
            return route.handler
        return None
    
    def get_api_routes(self, plugin_name: str = None) -> List[ApiRoute]:
        """Get all registered API routes, optionally filtered by plugin."""
        routes = list(self._api_routes.values())
        if plugin_name:
            routes = [r for r in routes if r.plugin_name == plugin_name]
        return routes
    
    def get_menu_items(self, sorted: bool = True) -> List[UIMenuItem]:
        """Get all registered menu items."""
        items = list(self._menu_items.values())
        if sorted:
            items.sort(key=lambda x: x.order)
        return items
    
    def get_pages(self) -> List[UIPage]:
        """Get all registered pages."""
        return list(self._pages.values())
    
    def get_setting_sections(self, sorted: bool = True) -> List[UISettingSection]:
        """Get all registered setting sections."""
        sections = list(self._setting_sections.values())
        if sorted:
            sections.sort(key=lambda x: x.order)
        return sections
    
    def get_widgets(self, position: str = None, sorted: bool = True) -> List[UIWidget]:
        """Get widgets, optionally filtered by position."""
        widgets = list(self._widgets.values())
        if position:
            widgets = [w for w in widgets if w.position == position]
        if sorted:
            widgets.sort(key=lambda x: x.order)
        return widgets
    
    def get_modals(self) -> List[UIModal]:
        """Get all registered modals."""
        return list(self._modals.values())
    
    def execute_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Execute all callbacks for a hook."""
        results = []
        callbacks = self._custom_hooks.get(hook_name, [])
        
        for callback in callbacks:
            try:
                result = callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Hook '{hook_name}' callback failed: {e}")
        
        return results
    
    def unregister_plugin(self, plugin_name: str) -> None:
        """Remove all UI elements registered by a plugin."""
        prefix = f"{plugin_name}."
        
        # Remove menu items
        self._menu_items = {k: v for k, v in self._menu_items.items() 
                          if not k.startswith(prefix)}
        
        # Remove pages
        self._pages = {k: v for k, v in self._pages.items() 
                      if not k.startswith(prefix)}
        
        # Remove setting sections
        self._setting_sections = {k: v for k, v in self._setting_sections.items() 
                                 if not k.startswith(prefix)}
        
        # Remove widgets
        self._widgets = {k: v for k, v in self._widgets.items() 
                        if not k.startswith(prefix)}
        
        # Remove modals
        self._modals = {k: v for k, v in self._modals.items() 
                       if not k.startswith(prefix)}
        
        # Remove API routes
        self._api_routes = {k: v for k, v in self._api_routes.items()
                           if not k.startswith(f"{plugin_name}:")}
        
        # Remove hooks (this is trickier, would need to track which callbacks belong to which plugin)
        # For now, we'll leave hooks in place
        
        logger.info(f"Unregistered all UI elements for plugin '{plugin_name}'")
    
    def to_dict(self) -> dict:
        """Export registry state as dictionary."""
        return {
            "menu_items": [item.to_dict() for item in self.get_menu_items()],
            "pages": [page.to_dict() for page in self.get_pages()],
            "setting_sections": [section.to_dict() for section in self.get_setting_sections()],
            "widgets": [widget.to_dict() for widget in self.get_widgets()],
            "modals": [modal.to_dict() for modal in self.get_modals()],
            "api_routes": [route.to_dict() for route in self.get_api_routes()],
            "available_hooks": list(self._custom_hooks.keys())
        }


# Global registry instance
ui_registry = PluginUIRegistry()
