import pygame
import time
import pyscreenshot
import sys
import subprocess
import os
import re

OUTPUT_DIRECTORY = os.path.expanduser("~/Downloads")
TOOL_SIZE = 2
tools_origin = [10, 40]

palette_width = 400.0
palette_height = 30

# https://www.webucator.com/blog/2015/03/python-color-constants-module/
palette = ["red", "green", "blue", "brown1", "darkorange"]
# TODO add non geometric tools (pointer, zoom)
available_tools = ['line', 'rect', 'circle']

def run_cmd(cmd, cwd):
    if not os.path.exists(cwd):
        if '-v' in sys.argv:
            print("path does not exist: %s" % cwd)
        return None
    if not os.path.isdir(cwd):
        if '-v' in sys.argv:
            print("path not a directory: %s" % cwd)
        return None
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check = False, cwd=cwd)
    if result.returncode != 0:
        if "-v" in sys.argv:
            print(("git status failed with exit code: %s. output below\n%s\n%s" % (result.returncode, result.stdout, result.stderr)).strip())
        return None

    stdout = result.stdout.decode("utf-8")
    if not stdout:
        return None

    return stdout

time_init = time.time()
colors = pygame.colordict.THECOLORS
active_color = colors['red']
active_indicator_color = colors['white']

pygame.init()

font = pygame.font.SysFont(None, 24)

active_text = font.render('active (ui: F7, undo: F8, color: F9, next tool: F10, tool size: F11(-)/F12(+))', True, colors['white'])
active_text_shadow = font.render('active (ui: F7, color: F8, undo: F9, next tool: F10, tool size: F11(-)/F12(+))', True, colors['black'])

im = pyscreenshot.grab(backend="scrot")
imbuffer = im.tobytes("raw", 'RGB')

def display_info():
    xrandr_out = run_cmd(["xrandr", "-q", "--current"], ".")
    display_idx = 0

    print()
    results = []

    for line in xrandr_out.split("\n"):
        if line.startswith("  ") or line.strip() == '':
            continue
        line = list(map(str.strip, line.strip().split()))
        display_name = line.pop(0)
        display_state = line.pop(0)
        if display_state.lower() != 'connected':
            continue

        display_rect = None
        for part in line:
            if re.match("\d+x\d+\+\d+\+\d+", part):
                part = list(map(int, part.replace("x", "+").split("+")))
                display_rect = {"dim": part[:2], "offset": part[2:]}
        print("display", "#%s" % display_idx, display_name, display_state, display_rect)
        results.append( {"id": display_idx, "name": display_name, "dim": display_rect["dim"], "offset": display_rect["offset"] } )
        display_idx += 1

    return results

target_display = None

if "--target" in sys.argv:
    args = list(sys.argv)
    target_display = args[args.index("--target") + 1]

def get_target(target_display):
    if not target_display:
        return None

    # try by number first
    for disp in display_info():
        if str(disp["id"]) == target_display:
            return disp
    # otherwise match names
    for disp in display_info():
        if target_display.lower() in disp["name"].lower():
            return disp
    return None

target_display = get_target(target_display)
print("target display", target_display)

screen = None

if target_display is None:
    screen = pygame.display.set_mode( (0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE )
else:
    os.environ['SDL_VIDEO_WINDOW_POS'] = '%s, %s' % (target_display['offset'][0], target_display['offset'][1])
    screen = pygame.display.set_mode( (target_display['dim'][0], target_display['dim'][1]), pygame.NOFRAME | pygame.DOUBLEBUF | pygame.HWSURFACE )

d_w, d_h = pygame.display.get_surface().get_size()
print("[screen] total size", im.width, im.height)

initial_screenshot = pygame.image.fromstring(imbuffer, (im.width, im.height), 'RGB')
pygame.image.save(initial_screenshot, "/home/frank/tmp/screen.png")
screen_crop_target = (0, 0)
screen_crop_source = None

if not target_display is None:
    rect = initial_screenshot.get_rect()
    screen_crop_target = (0, 0)
    screen_crop_source = [ target_display['offset'][0], target_display['offset'][1], target_display['dim'][0], target_display['dim'][1] ]

color_buttons = []

menu_offset = [50, 50]

active_tool = available_tools[0]

do_exit = False
counter = 0

clock = pygame.time.Clock()

gui_visible = True
# manager.set_visual_debug_mode(True)

def draw_indicator(screen):
    global gui_visible

    indicator_offset = (0, 0)
    indicator_interval = 1000
    cur_time = pygame.time.get_ticks()
    if gui_visible:
        screen.blit(active_text, (indicator_offset[0] + 35, indicator_offset[1] + 15))
        screen.blit(active_text, (indicator_offset[0] + 36, indicator_offset[1] + 16))
    indicator_color = colors['red'] if cur_time % (indicator_interval * 2) < indicator_interval else colors['coral']
    pygame.draw.circle(screen, indicator_color,
            (indicator_offset[0] + 21, indicator_offset[1] + 23),
            8, 0)

def save_current(screen):
    output_filename = None
    idx = 0
    for idx in range(10000):
        filename = "annotations_%s.png" % str(idx).zfill(4)
        output_filename = os.path.join(OUTPUT_DIRECTORY, filename)
        if not output_filename is None and not os.path.exists(output_filename):
            break

    print("[save] %s" % output_filename)
    pygame.image.save(screen, output_filename)

draw_stack = []

def is_mouse_over_palette():
    global tools_origin, palette_width, palette_height

    mouse_pos = pygame.mouse.get_pos()
    if mouse_pos[0] < tools_origin[0] or mouse_pos[0] > (tools_origin[0] + palette_width):
        return False
    if mouse_pos[1] < tools_origin[1] or mouse_pos[1] > (tools_origin[1] + palette_height):
        return False
    return True

def change_tool_size(delta):
    global TOOL_SIZE
    TOOL_SIZE += delta

    if TOOL_SIZE > 16:
        TOOL_SIZE = 16
    if TOOL_SIZE < 2:
        TOOL_SIZE = 2

def cycle_color(delta):
    global active_color
    active_pal_idx = 0
    for pal_idx, palette_col_name in enumerate(palette):
        if colors[palette_col_name] == active_color:
            active_pal_idx = pal_idx
    active_color = colors[ palette[ (active_pal_idx + delta) % len(palette) ] ]

def handle_event(event):
    global do_exit, gui_visible, draw_stack, TOOL_SIZE, active_tool, active_color
    if event.type == pygame.QUIT:
        print("[event] exit")
        do_exit = True
    elif event.type == pygame.MOUSEBUTTONDOWN:
        if not is_mouse_over_palette():
            if event.button == 4:
                change_tool_size(+2)
            if event.button == 5:
                change_tool_size(-2)
        else:
            if event.button == 4:
                cycle_color(+1)
            if event.button == 5:
                cycle_color(-1)
    elif event.type == pygame.KEYDOWN:
        print("[event] keydown %s" % event.key)
        if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
            print("[event] exiting on keypress")
            do_exit = True
        if event.key == pygame.K_F7:
            gui_visible = not gui_visible
        if event.key == pygame.K_F5:
            print("[event] save and exit")
            save_current(screen)
            do_exit = True
        if event.key == pygame.K_F10:
            tool_idx = available_tools.index(active_tool)
            active_tool = available_tools[ (tool_idx + 1) % len(available_tools) ]
        if event.key == pygame.K_F12:
            change_tool_size(+2)
        if event.key == pygame.K_F11:
            change_tool_size(-2)

        if event.key == pygame.K_F9:
            cycle_color(+1)
        if event.key == pygame.K_F8:
            if len(draw_stack) > 0:
                draw_stack.pop(len(draw_stack) - 1)
                print("[draw] undone")

    if event.type == pygame.USEREVENT:
         if event.user_type == pygame_gui.UI_BUTTON_PRESSED:
             for color_btn, colname, col in color_buttons:
                 if event.ui_element == color_btn:
                     print("[btn] %s" % colname)

def draw_stack_item(screen, item):
    active_tool, active_color, source_pos, end_pos, lwidth = item

    if source_pos:
        source_pos = list(map(int, source_pos))
    if end_pos:
        end_pos = list(map(int, end_pos))

    if active_tool == 'line':
        pygame.draw.line(screen, active_color, source_pos, end_pos, lwidth)
    elif active_tool == 'rect':
        rect = pygame.Rect(source_pos[0], source_pos[1], end_pos[0] - source_pos[0], end_pos[1] - source_pos[1])
        pygame.draw.rect(screen, active_color, rect, lwidth)
    elif active_tool == 'circle':
        radius = int(max(lwidth + 1, min(end_pos[0] - source_pos[0], end_pos[1] - source_pos[1]) ))
        pygame.draw.circle(screen, active_color, source_pos, radius, lwidth)

def draw_stack_content(screen):
    for item in draw_stack:
        draw_stack_item(screen, item)

active_mousedown = None

def add_to_draw_stack(active_tool, active_color, start_pos, end_pos):
    draw_stack.append( [active_tool, active_color, start_pos, end_pos, TOOL_SIZE] )
    print("[draw] add %s" % draw_stack[-1])

def handle_mouse(screen):
    global active_mousedown

    left_pressed, middle_pressed, right_pressed = pygame.mouse.get_pressed()
    mouse_pos = pygame.mouse.get_pos()

    if left_pressed:
        if active_mousedown is None:
            # initial click
            active_mousedown = mouse_pos

        draw_stack_item(screen, [active_tool, active_color, active_mousedown, mouse_pos, TOOL_SIZE])
        pygame.draw.circle(screen, colors['red'], (pygame.mouse.get_pos()), 2)
    else:
        # mouse not clicked anymore
        if not active_mousedown is None:
            # this completes an action, put it on the stack
            add_to_draw_stack(active_tool, active_color, active_mousedown, mouse_pos)
            active_mousedown = None

def draw_tools(screen):
    global gui_visible, tools_origin, palette_width, palette_height
    if not gui_visible:
        return

    tools_offset = tools_origin.copy()
    active_indicator = 5
    entry_width = int(palette_width / len(palette))

    idx = 0
    for pal_color_name in palette:
        pal_color = colors[pal_color_name]

        entry_rect = [tools_offset[0] + (idx * entry_width), tools_offset[1], entry_width, palette_height]
        pygame.draw.rect(screen, pal_color, entry_rect, 0)

        if pal_color == active_color:
            indicator_rect = entry_rect
            indicator_rect[1] += indicator_rect[3] - active_indicator
            indicator_rect[3] = active_indicator
            pygame.draw.rect(screen, active_indicator_color, indicator_rect, 0)

        idx += 1

    tools_offset[0] += palette_width + 20
    tools_offset_end = list(tools_offset)
    pygame.draw.rect(screen, active_indicator_color, [tools_offset[0], tools_offset[1], palette_height, palette_height], 0)

    if active_tool == 'circle':
        tools_offset[0] += palette_height / 2
        tools_offset[1] += palette_height / 2

    tools_offset_end[0] += palette_height
    tools_offset_end[1] += palette_height

    preview_tool = [ active_tool, active_color, tools_offset, tools_offset_end, TOOL_SIZE]
    draw_stack_item(screen, preview_tool)

first_frame = True

while counter < 1000 and not do_exit:
    counter += 1

    for event in pygame.event.get():
        handle_event(event)

    pygame.time.wait(10)

    # screenshot background
    screen.blit(initial_screenshot, screen_crop_target, screen_crop_source)

    draw_indicator(screen)

    draw_tools(screen)

    draw_stack_content(screen)

    handle_mouse(screen)

    pygame.display.update()
    if first_frame:
        first_frame = False
        print('time to first frame:', time.time() - time_init)

pygame.quit()
sys.exit(0)
