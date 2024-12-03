import curses
import threading
import Quartz.CoreGraphics as CG
import time

# Constants
SCENE_WIDTH_MULTIPLIER = 4  # Scene width as a multiple of terminal width
SCENE_HEIGHT_MULTIPLIER = 3  # Scene height as a multiple of terminal height
SCROLL_SPEED = 0.2  # Speed multiplier for smooth scrolling

# State variables
scene_offset = 0  # Horizontal offset of the scene
vertical_offset = 0  # Vertical offset of the scene
mouse_delta_buffer = [0, 0]  # Buffered mouse deltas for smooth updates


def lock_mouse_to_center():
    """Lock the mouse to the center of the screen."""
    screen_bounds = CG.CGDisplayBounds(CG.CGMainDisplayID())
    center_x = screen_bounds.size.width / 2
    center_y = screen_bounds.size.height / 2
    CG.CGWarpMouseCursorPosition((center_x, center_y))
    return center_x, center_y


def mouse_event_callback(proxy, event_type, event, refcon):
    """Callback to handle mouse movement events."""
    global mouse_delta_buffer

    if event_type == CG.kCGEventMouseMoved:
        # Extract relative movement
        dx = CG.CGEventGetIntegerValueField(event, CG.kCGMouseEventDeltaX)
        dy = CG.CGEventGetIntegerValueField(event, CG.kCGMouseEventDeltaY)

        # Update the delta buffer atomically
        mouse_delta_buffer[0] += dx
        mouse_delta_buffer[1] -= dy  # Invert Y for typical screen coordinates

        # Lock the mouse to the center of the screen
        lock_mouse_to_center()
    return event


def start_mouse_listener():
    """Start a global event tap to listen for mouse movements."""
    # Detach the mouse cursor rendering from its events
    CG.CGAssociateMouseAndMouseCursorPosition(False)

    # Hide the mouse cursor
    CG.CGDisplayHideCursor(CG.CGMainDisplayID())

    event_mask = CG.CGEventMaskBit(CG.kCGEventMouseMoved)
    event_tap = CG.CGEventTapCreate(
        CG.kCGHIDEventTap,
        CG.kCGHeadInsertEventTap,
        CG.kCGEventTapOptionDefault,
        event_mask,
        mouse_event_callback,
        None,
    )
    if not event_tap:
        raise Exception("Unable to create event tap.")
    run_loop_source = CG.CFMachPortCreateRunLoopSource(None, event_tap, 0)
    CG.CFRunLoopAddSource(
        CG.CFRunLoopGetCurrent(), run_loop_source, CG.kCFRunLoopCommonModes
    )
    CG.CGEventTapEnable(event_tap, True)
    CG.CFRunLoopRun()


def generate_scene(width, height):
    """Generate a basic scene."""
    scene = [[" " for _ in range(width)] for _ in range(height)]

    # Add an object to the scene for visual reference
    for i in range(5, 15):
        scene[10][i] = "#"

    return scene


def render_scene(stdscr):
    """Render the scene and crosshair."""
    global scene_offset, vertical_offset, mouse_delta_buffer
    curses.curs_set(0)  # Hide the terminal cursor
    stdscr.nodelay(True)

    # Get terminal dimensions
    max_y, max_x = stdscr.getmaxyx()
    scene_width = max_x * SCENE_WIDTH_MULTIPLIER
    scene_height = max_y * SCENE_HEIGHT_MULTIPLIER

    # Generate the scene
    scene = generate_scene(scene_width, scene_height)

    while True:
        # Clear the screen
        stdscr.clear()

        # Safely consume buffered deltas
        dx, dy = mouse_delta_buffer[0], mouse_delta_buffer[1]
        mouse_delta_buffer = [0, 0]

        # Increment raw offsets based on buffered deltas
        scene_offset -= dx * SCROLL_SPEED  # Invert horizontal movement
        vertical_offset += dy * SCROLL_SPEED

        # Calculate visible portion using modulo for wrapping
        visible_start_x = int(scene_offset) % scene_width
        visible_start_y = int(vertical_offset) % scene_height

        for row in range(max_y):
            actual_y = (visible_start_y + row) % scene_height
            visible_end_x = visible_start_x + max_x
            if visible_end_x < scene_width:
                line = "".join(scene[actual_y][visible_start_x:visible_end_x])
            else:
                part1 = scene[actual_y][visible_start_x:scene_width]
                part2 = scene[actual_y][0:visible_end_x - scene_width]
                line = "".join(part1 + part2)

            # Safeguard rendering
            try:
                stdscr.addstr(row, 0, line[:max_x])
            except curses.error:
                pass

        # Draw the crosshair at the center of the terminal
        crosshair_row = max_y // 2
        crosshair_col = max_x // 2
        try:
            stdscr.addch(crosshair_row, crosshair_col, "+")
        except curses.error:
            pass

        # Re-hide the mouse cursor
        CG.CGDisplayHideCursor(CG.CGMainDisplayID())

        # Refresh the screen
        stdscr.refresh()


def enforce_cursor_hidden():
    """Continuously ensure the mouse cursor remains hidden."""
    while True:
        CG.CGDisplayHideCursor(CG.CGMainDisplayID())
        time.sleep(0.1)  # Run periodically to maintain the hidden state


# Start the cursor hiding thread before anything else
cursor_hide_thread = threading.Thread(target=enforce_cursor_hidden, daemon=True)
cursor_hide_thread.start()

# Start the mouse listener in a separate thread
mouse_listener_thread = threading.Thread(target=start_mouse_listener, daemon=True)
mouse_listener_thread.start()

# Run the curses renderer
curses.wrapper(render_scene)
