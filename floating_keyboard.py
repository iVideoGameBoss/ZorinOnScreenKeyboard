#!/usr/bin/env python3
"""
Floating On-Screen Keyboard
A resizable, always-on-top virtual keyboard that sends keystrokes to the focused window.
"""

import tkinter as tk
import subprocess


class FloatingKeyboard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("On-Screen Keyboard")
        
        # Track target window - must be set BEFORE override_redirect
        self.target_window = None
        self.keyboard_window_id = None
        
        # Track shift and caps state
        self.shift_active = False
        self.caps_active = False
        
        # Color Themes
        self.themes = {
            'dark': {
                'bg': '#2b2b2b',
                'fg': '#ffffff',
                'key_bg': '#4a4a4a',   # Dark keys for dark mode
                'key_fg': '#dddddd',   # Light grey text
                'title_bg': '#404040',
                'title_fg': '#ffffff',
                'active_bg': '#606060',
                'shift_bg': '#007acc', # Blue-ish for active shift in dark mode
                'caps_bg': '#009900'   # Green-ish for active caps in dark mode
            },
            'light': {
                'bg': '#e0e0e0',
                'fg': '#000000',
                'key_bg': '#ffffff',
                'key_fg': '#000000',
                'title_bg': '#d0d0d0',
                'title_fg': '#000000',
                'active_bg': '#c0c0c0',
                'shift_bg': '#87CEEB',
                'caps_bg': '#90EE90'
            }
        }
        self.current_theme = 'dark'
        
        # Set initial size and position
        self.root.geometry("920x250+100+500")
        
        # Make window not managed by WM (won't steal focus)
        self.root.overrideredirect(True)
        
        # Keep on top
        self.root.attributes('-topmost', True)
        
        # Variables for dragging
        self._drag_x = 0
        self._drag_y = 0
        self.is_minimized = False
        self.restored_height = 250
        
        # Title bar for dragging - Packed at BOTTOM
        self.title_bar = tk.Frame(self.root, bg='#404040', height=25)
        self.title_bar.pack(fill='x', side='bottom')
        self.title_bar.pack_propagate(False)
        
        # Title label
        title_label = tk.Label(self.title_bar, text="On-Screen Keyboard", bg='#404040', fg='white', font=('Arial', 10))
        title_label.pack(side='left', padx=10)
        
        # Bind double-click to reset size
        self.title_bar.bind('<Double-Button-1>', self.reset_window_size)
        title_label.bind('<Double-Button-1>', self.reset_window_size)
        
        # Close button - Pack FIRST to be rightmost
        # Auto width to fit text
        button_padding = 2
        close_btn = tk.Button(self.title_bar, text='X', bg='#404040', fg='white', 
                              bd=0, font=('Arial', 10), command=self.root.quit,
                              activebackground='#cc0000', activeforeground='white',
                              padx=button_padding)
        # Increased right padding to avoid overlap with resize grip
        close_btn.pack(side='right', padx=(0, 20))
        
        # Minimize button - Pack SECOND to be to the left of Close
        # Auto width to fit text
        self.min_btn = tk.Button(self.title_bar, text='-', bg='#404040', fg='white', 
                              bd=0, font=('Arial', 10), command=self.toggle_minimize,
                              activebackground='#606060', activeforeground='white',
                              padx=2)
        self.min_btn.pack(side='right', padx=2)
        
        # Theme toggle button - Pack THIRD (right to left)
        # Auto width to fit text
        self.theme_btn = tk.Button(self.title_bar, text='☀/🌙', bg='#404040', fg='white',
                                 bd=0, font=('Arial', 10), command=self.toggle_theme,
                                 activebackground='#606060', activeforeground='white',
                                 padx=2)
        self.theme_btn.pack(side='right', padx=2)
        
        # Select window button
        select_btn = tk.Button(self.title_bar, text='Select Window', bg='#505050', fg='white',
                               bd=0, font=('Arial', 10), command=self.select_target_window,
                               activebackground='#606060')
        select_btn.pack(side='right', padx=10)
        
        # Status label
        self.status_label = tk.Label(self.title_bar, text='No target', bg='#404040', fg='#aaaaaa', font=('Arial', 10))
        self.status_label.pack(side='right', padx=5)
        
        # Bind drag events to title bar
        self.title_bar.bind('<Button-1>', self.start_drag)
        self.title_bar.bind('<B1-Motion>', self.do_drag)
        title_label.bind('<Button-1>', self.start_drag)
        title_label.bind('<B1-Motion>', self.do_drag)
        
        # Main frame
        self.main_frame = tk.Frame(self.root, bg='#2b2b2b')
        self.main_frame.pack(fill='both', expand=True, padx=2, pady=2)
        
        # Configure rows to expand
        for i in range(5):
            self.main_frame.grid_rowconfigure(i, weight=1)
            
        # Stop grid propagation so buttons don't force frame size
        self.main_frame.grid_propagate(False)
        
        # Shift character mappings
        self.shift_map = {
            '`': '~', '1': '!', '2': '@', '3': '#', '4': '$', '5': '%',
            '6': '^', '7': '&', '8': '*', '9': '(', '0': ')', '-': '_',
            '=': '+', '[': '{', ']': '}', '\\': '|', ';': ':', "'": '"',
            ',': '<', '.': '>', '/': '?'
        }
        
        self.buttons = {}
        self.create_keyboard()
        
        # Resize grip
        self.resize_grip = tk.Frame(self.root, bg='#606060', width=15, height=15, cursor='bottom_right_corner')
        self.resize_grip.place(relx=1.0, rely=1.0, anchor='se')
        self.resize_grip.bind('<Button-1>', self.start_resize)
        self.resize_grip.bind('<B1-Motion>', self.do_resize)
        
        # Apply initial theme
        self.apply_theme()
    
    def start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y
    
    def do_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")
    
    def toggle_minimize(self):
        """Toggle between minimized (title bar only) and restored state"""
        if self.is_minimized:
            # Restore
            y_now = self.root.winfo_y()
            # Calculate new y to keep bottom edge constant
            new_y = y_now - (self.restored_height - 25)
            
            self.root.geometry(f"{self.root.winfo_width()}x{self.restored_height}+{self.root.winfo_x()}+{new_y}")
            self.main_frame.pack(fill='both', expand=True, padx=2, pady=2, side='top')
            self.resize_grip.place(relx=1.0, rely=1.0, anchor='se')
            self.min_btn.configure(text='-')
            self.is_minimized = False
        else:
            # Minimize
            self.restored_height = self.root.winfo_height()
            y_now = self.root.winfo_y()
            
            self.main_frame.pack_forget()
            self.resize_grip.place_forget()
            
            # Calculate new y to keep bottom edge constant
            new_y = y_now + (self.restored_height - 25)
            
            # Height of title bar (25) + optional small padding
            self.root.geometry(f"{self.root.winfo_width()}x25+{self.root.winfo_x()}+{new_y}")
            self.min_btn.configure(text='+')
            self.is_minimized = True

    def start_resize(self, event):
        if self.is_minimized:
            return
        self._resize_x = event.x_root
        self._resize_y = event.y_root
        self._resize_w = self.root.winfo_width()
        self._resize_h = self.root.winfo_height()
    
    
    def reset_window_size(self, event=None):
        """Reset window to default size"""
        # Only reset if not minimized
        if not self.is_minimized:
            # Default size from __init__
            self.root.geometry("920x250")
            # Update internal resize tracking
            self._resize_w = 920
            self._resize_h = 250
            # Update font scaling
            self.update_font_size(920)

    def do_resize(self, event):
        new_w = max(500, self._resize_w + (event.x_root - self._resize_x))
        new_h = max(150, self._resize_h + (event.y_root - self._resize_y))
        self.root.geometry(f"{new_w}x{new_h}")
        self.update_font_size(new_w)
        
    def update_font_size(self, width):
        """Update font size based on window width"""
        # Base width is 920, so scale factor is width / 920
        # But let's scale bit more aggressively for small sizes
        scale = width / 920.0
        
        for btn in self.buttons.values():
            if hasattr(btn, 'base_font_size'):
                # 3 is the standard size. If scale is 0.65 (600/920), 3 * 0.65 = 1.95 -> 1
                new_size = max(1, int(btn.base_font_size * scale))
                current_font = btn.cget('font')
                # Check if we need to update (font is a string or tuple)
                # Tkinter returns font as string usually, but we set it as tuple
                # Simple check: just update it, it's cheap enough
                btn.configure(font=('Arial', new_size))
        
    def create_key(self, parent, text, keycode, row, col, colspan=1, font_size=12):
        """Create a single key button"""
        btn = tk.Button(
            parent,
            text=text,
            font=('Arial', font_size),
            bg='#f0f0f0',
            activebackground='#d0d0d0',
            relief='raised',
            bd=0,
            padx=0,
            pady=0,
            highlightthickness=0,
            takefocus=False,
            command=lambda: self.on_key_press(keycode, text)
        )
        btn.grid(row=row, column=col, columnspan=colspan, sticky='nsew', padx=1, pady=1)
        btn.base_font_size = font_size
        self.buttons[(text, keycode)] = btn
        return btn
        
    def create_keyboard(self):
        """Create the keyboard layout"""
        # Use 30 columns total for fine-grained control
        for i in range(30):
            self.main_frame.grid_columnconfigure(i, weight=1, uniform='key')
        
        # Row 0: Number row
        keys_row0 = [('`', 'grave'), ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'),
                     ('5', '5'), ('6', '6'), ('7', '7'), ('8', '8'), ('9', '9'),
                     ('0', '0'), ('-', 'minus'), ('=', 'equal')]
        col = 0
        for text, keycode in keys_row0:
            self.create_key(self.main_frame, text, keycode, 0, col, colspan=2)
            col += 2
        self.create_key(self.main_frame, 'Backspace', 'BackSpace', 0, col, colspan=4, font_size=10)
        
        # Row 1: Tab + QWERTY
        self.create_key(self.main_frame, 'Tab', 'Tab', 1, 0, colspan=3, font_size=10)
        keys_row1 = ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p']
        col = 3
        for key in keys_row1:
            self.create_key(self.main_frame, key, key, 1, col, colspan=2)
            col += 2
        self.create_key(self.main_frame, '[', 'bracketleft', 1, col, colspan=2)
        col += 2
        self.create_key(self.main_frame, ']', 'bracketright', 1, col, colspan=2)
        col += 2
        self.create_key(self.main_frame, '\\', 'backslash', 1, col, colspan=3)
        
        # Row 2: Caps + ASDF
        self.create_key(self.main_frame, 'Caps', 'Caps_Lock', 2, 0, colspan=4, font_size=10)
        keys_row2 = ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l']
        col = 4
        for key in keys_row2:
            self.create_key(self.main_frame, key, key, 2, col, colspan=2)
            col += 2
        self.create_key(self.main_frame, ';', 'semicolon', 2, col, colspan=2)
        col += 2
        self.create_key(self.main_frame, "'", 'apostrophe', 2, col, colspan=2)
        col += 2
        self.create_key(self.main_frame, 'Enter', 'Return', 2, col, colspan=4, font_size=10)
        
        # Row 3: Shift + ZXCV
        self.create_key(self.main_frame, 'Shift', 'Shift_L', 3, 0, colspan=5, font_size=10)
        keys_row3 = ['z', 'x', 'c', 'v', 'b', 'n', 'm']
        col = 5
        for key in keys_row3:
            self.create_key(self.main_frame, key, key, 3, col, colspan=2)
            col += 2
        self.create_key(self.main_frame, ',', 'comma', 3, col, colspan=2)
        col += 2
        self.create_key(self.main_frame, '.', 'period', 3, col, colspan=2)
        col += 2
        self.create_key(self.main_frame, '/', 'slash', 3, col, colspan=2)
        col += 2
        self.create_key(self.main_frame, 'Shift', 'Shift_R', 3, col, colspan=5, font_size=10)
        
        # Row 4: Bottom row
        self.create_key(self.main_frame, 'Ctrl', 'Control_L', 4, 0, colspan=3, font_size=10)
        self.create_key(self.main_frame, 'Win', 'Super_L', 4, 3, colspan=3, font_size=10)
        self.create_key(self.main_frame, 'Alt', 'Alt_L', 4, 6, colspan=3, font_size=10)
        self.create_key(self.main_frame, 'Space', 'space', 4, 9, colspan=12, font_size=10)
        self.create_key(self.main_frame, 'Alt', 'Alt_R', 4, 21, colspan=3, font_size=10)
        self.create_key(self.main_frame, 'Win', 'Super_R', 4, 24, colspan=3, font_size=10)
        self.create_key(self.main_frame, 'Ctrl', 'Control_R', 4, 27, colspan=3, font_size=10)
    
    def select_target_window(self):
        """Let user click to select target window"""
        try:
            # Hide keyboard temporarily
            self.root.withdraw()
            self.root.update()
            
            # Use xdotool to let user select a window
            result = subprocess.run(['xdotool', 'selectwindow'], capture_output=True, text=True)
            if result.stdout.strip():
                self.target_window = result.stdout.strip()
                # Get window name for display
                name_result = subprocess.run(['xdotool', 'getwindowname', self.target_window],
                                            capture_output=True, text=True)
                window_name = name_result.stdout.strip()[:20] if name_result.stdout.strip() else 'Unknown'
                self.status_label.configure(text=f'Target: {window_name}', fg='#90EE90')
                # print(f"Target window set: {self.target_window} ({window_name})")
            
            # Show keyboard again
            self.root.deiconify()
            self.root.lift()
            
        except Exception as e:
            print(f"Error selecting window: {e}")
            self.root.deiconify()
    
    def get_target_window(self):
        """Get the window that should receive keystrokes"""
        try:
            # Get our own window ID
            if self.keyboard_window_id is None:
                result = subprocess.run(['xdotool', 'search', '--name', 'On-Screen Keyboard'],
                                       capture_output=True, text=True)
                if result.stdout.strip():
                    self.keyboard_window_id = result.stdout.strip().split()[0]
            
            # Get the currently active window
            result = subprocess.run(['xdotool', 'getactivewindow'], capture_output=True, text=True)
            current = result.stdout.strip()
            
            # If active window is not the keyboard, use it as target
            if current and current != self.keyboard_window_id:
                self.target_window = current
                
        except Exception as e:
            print(f"Error getting target window: {e}")
    
    def send_key(self, keycode):
        """Send a key to the target window using xdotool"""
        try:
            if not self.target_window:
                # print("No target window set. Click 'Select Window' first.")
                return
            
            # print(f"Sending '{keycode}' to window {self.target_window}")
            
            # Activate the target window first
            subprocess.run(['xdotool', 'windowactivate', '--sync', self.target_window], 
                          capture_output=True, check=False)
            
            # For single printable characters, use type
            if len(keycode) == 1:
                subprocess.run(['xdotool', 'type', '--clearmodifiers', keycode])
            else:
                # For special keys (BackSpace, Return, etc), use key
                subprocess.run(['xdotool', 'key', '--clearmodifiers', keycode])
            
            # Bring keyboard back on top
            self.root.deiconify()
            self.root.lift()
            self.root.attributes('-topmost', True)
                    
        except subprocess.CalledProcessError as e:
            print(f"Error sending key: {e}")
        except FileNotFoundError:
            print("xdotool not found. Please install: sudo apt install xdotool")
    
    def on_key_press(self, keycode, display):
        """Handle key button press"""
        # Handle Shift
        if keycode in ('Shift_L', 'Shift_R'):
            self.shift_active = not self.shift_active
            self.update_key_display()
            return
        
        # Handle Caps Lock
        if keycode == 'Caps_Lock':
            self.caps_active = not self.caps_active
            self.update_key_display()
            self.send_key(keycode)
            return
        
        # Handle letter keys
        if len(display) == 1 and display.isalpha():
            if self.shift_active or self.caps_active:
                self.send_key(keycode.upper())
            else:
                self.send_key(keycode)
        # Handle shifted symbols
        elif self.shift_active and display in self.shift_map:
            shifted = self.shift_map[display]
            if self.target_window:
                subprocess.run(['xdotool', 'type', '--window', self.target_window, '--', shifted])
        else:
            self.send_key(keycode)
        
        # Reset shift after key press
        if self.shift_active:
            self.shift_active = False
            self.update_key_display()
    
    def toggle_theme(self):
        """Switch between dark and light mode"""
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.apply_theme()
        
    def apply_theme(self):
        """Apply current theme colors to all widgets"""
        theme = self.themes[self.current_theme]
        
        # Update main window and frames
        self.root.configure(bg=theme['bg'])
        self.main_frame.configure(bg=theme['bg'])
        self.title_bar.configure(bg=theme['title_bg'])
        
        # Update title bar widgets
        # Note: We need to keep references if we want to update them easily
        # For now, let's update known widgets
        for widget in self.title_bar.winfo_children():
            if isinstance(widget, tk.Button):
                widget.configure(bg=theme['title_bg'], fg=theme['title_fg'],
                               activebackground=theme['active_bg'], activeforeground=theme['title_fg'])
            elif isinstance(widget, tk.Label):
                widget.configure(bg=theme['title_bg'], fg=theme['title_fg'])
                
        # Status label might need specific color
        if self.target_window:
             self.status_label.configure(fg='#90EE90' if self.current_theme == 'dark' else '#006400')
        else:
             self.status_label.configure(fg='#aaaaaa' if self.current_theme == 'dark' else '#666666')

        # Update Keys
        for key_btn in self.buttons.values():
            # Check special keys to maintain their state colors if active
            # This is handled by update_key_display usually, but let's reset base colors
            key_btn.configure(bg=theme['key_bg'], fg=theme['key_fg'],
                            activebackground=theme['active_bg'])
                            
        # Re-apply state colors (Shift/Caps)
        self.update_key_display()

    def update_key_display(self):
        """Update key labels and highlights"""
        theme = self.themes[self.current_theme]
        
        for (display, keycode), btn in self.buttons.items():
            # Update shift/caps button colors
            if keycode in ('Shift_L', 'Shift_R'):
                btn.configure(bg=theme['shift_bg'] if self.shift_active else theme['key_bg'],
                            relief='sunken' if self.shift_active else 'raised')
            elif keycode == 'Caps_Lock':
                btn.configure(bg=theme['caps_bg'] if self.caps_active else theme['key_bg'],
                            relief='sunken' if self.caps_active else 'raised')
            else:
                # Ensure normal keys have correct theme color
                btn.configure(bg=theme['key_bg'], fg=theme['key_fg'])
                
                # Determine display text based on state
                new_text = display
                
                # Handle Shift state
                if self.shift_active:
                    if display in self.shift_map:
                        new_text = self.shift_map[display]
                    elif len(display) == 1 and display.isalpha():
                        new_text = display.upper()
                # Handle Normal state (respecting Caps Lock for letters)
                else:
                    if len(display) == 1 and display.isalpha():
                        if self.caps_active:
                            new_text = display.upper()
                        else:
                            new_text = display.lower()
                            
                # Update button text if changed
                if btn.cget('text') != new_text:
                    btn.configure(text=new_text)
    
    def run(self):
        # Get initial target window (whatever is focused when keyboard starts)
        self.get_target_window()
        self.root.mainloop()


def main():
    # Check for xdotool
    try:
        subprocess.run(['which', 'xdotool'], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("xdotool is required! Install with: sudo apt install xdotool")
        return
    
    keyboard = FloatingKeyboard()
    keyboard.run()


if __name__ == "__main__":
    main()
