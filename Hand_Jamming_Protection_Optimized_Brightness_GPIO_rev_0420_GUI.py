import time, os, sys
from media.sensor import *
from media.display import *
from media.media import *
import image

from ybUtils.YbUart import YbUart
from machine import Pin
from machine import FPIOA
from machine import TOUCH

# Initialize touch sensor
tp = TOUCH(0)

fpioa = FPIOA()
fpioa.set_function(33, FPIOA.GPIO43) # Connect external controller，GPIO33
fpioa.set_function(42, FPIOA.GPIO42) # Connect external controller，GPIO42
fpioa.set_function(43, FPIOA.GPIO43) # Connect external controller，GPIO43

SIG_SYSTEMON = Pin(33, Pin.OUT) # Connect external controller, GPIO Output
SIG_ALARM_1 = Pin(42, Pin.OUT) # Connect external controller, GPIO Output
SIG_ALARM_2 = Pin(43, Pin.OUT) # Connect external controller, GPIO Output

# Display parameters
DISPLAY_WIDTH = 640   # LCD display width
DISPLAY_HEIGHT = 480  # LCD display height

# LAB color space thresholds
# (L Min, L Max, A Min, A Max, B Min, B Max)
THRESHOLDS = [
    ((15, 100, -25, 15, 18, 60))    # yellow colored tape object (wide L for brightness robustness)
]

# Reference average L brightness the base threshold was tuned at.
# Used by compute_adaptive_threshold() to shift the L window.
REF_BRIGHTNESS = 55

# Screen Center Point Coordinate
SCREEN_CENTER = DISPLAY_WIDTH // 2

# Max distinct objects to track
MAX_OBJECTS = 3

# Second-stage blob filter parameters
MIN_BLOB_PIXELS = 120
MIN_FILL_RATIO = 0.20

# Blob detection behavior tuning
PIXELS_THRESHOLD = 120
AREA_THRESHOLD = 120
MERGE_BLOBS = False
MERGE_MARGIN = 2

# Temporal smoothing for bounding box stability
SMOOTH_ALPHA = 0.35

# Variable for Hand Jamming Protection Loop
TRIG_PROTECT = False # Hand Jamming Protection Feature Trigger
MAX_TOP_W = 220         # Maximum width of the yellow strip on top
MAX_TOP_H = 15          # Maximum height of the yellow strip on top
MAX_SIDE_W = 30        # Maximum width of the yellow strip on side
MAX_SIDE_H = 80         # Maximum height of the yellow strip on side
THRE_ERR_SIDE_W = 10     # Threshold of error of width between yellow strips on both side
THRE_ERR_SIDE_H = 10    # Threshold of error of height between yellow strips on both side
THRE_ERR_TOP_W = 10     # Threshold of error of width between max. value and top yellow strip
THRE_ERR_TOP_H = 10      # Threshold of error of height between max. value and top yellow strip

# On-screen input UI layout (upper-right corner)
UI_LABEL_X  = 480
UI_LABEL_Y  = 2
VAL_BOX     = (480, 22, 44, 24)
BTN_PLUS    = (530, 22, 28, 24)
BTN_MINUS   = (562, 22, 28, 24)
BTN_OK      = (594, 22, 40, 24)
input_value      = MAX_TOP_H   # Editing value shown in the input box

class DrawingApp:
    def __init__(self):
        """初始化绘画应用程序"""
        # 绘画状态
        self.current_color = (0, 0, 0)  # 当前颜色（黑色）
        self.current_brush_size = 5     # 当前画笔大小
        self.is_drawing = False         # 是否正在绘画
        self.last_x = None             # 上一个触摸点X坐标
        self.last_y = None             # 上一个触摸点Y坐标

        # 颜色调色板
        self.colors = [
            (0, 0, 0),       # 黑色
            (255, 0, 0),     # 红色
            (0, 255, 0),     # 绿色
            (0, 0, 255),     # 蓝色
            (255, 255, 0),   # 黄色
            (255, 0, 255),   # 紫色
            (0, 255, 255),   # 青色
            (255, 128, 0),   # 橙色
            (128, 0, 128),   # 深紫色
            (255, 255, 255), # 白色（橡皮擦）
        ]

        # 画笔大小选项
        self.brush_sizes = [2, 5, 8, 12, 16, 20]
        self.current_brush_index = 1  # 默认选择5像素

        # UI区域定义
        self.color_palette_y = 50
        self.color_size = 25
        self.color_spacing = 30

        self.brush_palette_y = 200
        self.brush_button_height = 25
        self.brush_spacing = 30

        self.control_buttons_y = 380
        self.button_width = 120
        self.button_height = 35

        # 创建单一显示图像，避免复杂的像素操作
        self.display_image = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.RGB888)

        # 初始化显示
        self.clear_canvas()
        self.draw_ui()
        self.update_display()

    def clear_canvas(self):
        """清空画布"""
        # 清空整个显示图像
        self.display_image.clear()
        # 绘制白色画布背景
        self.display_image.draw_rectangle(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT,
                                        color=(255, 255, 255), fill=True)
        # 绘制工具栏背景
        self.display_image.draw_rectangle(CANVAS_WIDTH, 0, TOOLBAR_WIDTH, CANVAS_HEIGHT,
                                        color=(240, 240, 240), fill=True)
        # 绘制分隔线
        self.display_image.draw_line(CANVAS_WIDTH, 0, CANVAS_WIDTH, CANVAS_HEIGHT,
                                   color=(200, 200, 200), thickness=2)

    def draw_ui(self):
        """绘制用户界面"""
        # 绘制控制按钮
        self.draw_control_buttons()


    def draw_control_buttons(self):
        """绘制控制按钮"""
        buttons = ["Clear", "Cancel"]
        button_colors = [(255, 200, 200), (200, 255, 200)]

        for i, (text, color) in enumerate(zip(buttons, button_colors)):
            y = self.control_buttons_y + i * (self.button_height + 10)

            # 按钮背景
            self.display_image.draw_rectangle(CANVAS_WIDTH + 20, y, self.button_width, self.button_height,
                                            color=color, fill=True)

            # 按钮边框
            self.display_image.draw_rectangle(CANVAS_WIDTH + 20, y, self.button_width, self.button_height,
                                            color=(100, 100, 100), fill=False)

            # 按钮文字
            # 英文备选
            en_text = "Clear" if i == 0 else "Undo"
            self.display_image.draw_string_advanced(CANVAS_WIDTH + 30, y + 8, 16,
                                                   en_text, color=(50, 50, 50))

    def handle_control_buttons(self, x, y):
        """处理控制按钮"""
        if CANVAS_WIDTH + 20 <= x <= CANVAS_WIDTH + 20 + self.button_width:
            rel_y = y - self.control_buttons_y
            button_index = rel_y // (self.button_height + 10)

            if button_index == 0:  # 清屏按钮
                self.clear_canvas()
                self.draw_ui()
                print("清空画布")
            elif button_index == 1:  # 撤销按钮
                print("撤销功能（待实现）")

    def update_display(self):
        """更新显示 - 简化版本，避免像素级操作"""
        Display.show_image(self.display_image)


class BlobObj:
    """Wraps a raw blob with named attribute access.
    Supports index access (blob[0:4], blob[4], etc.) so existing code is unchanged."""
    def __init__(self, raw_blob):
        self._blob = raw_blob
        self.x      = raw_blob[0]
        self.y      = raw_blob[1]
        self.w      = raw_blob[2]
        self.h      = raw_blob[3]
        self.pixels = raw_blob[4]
        self.cx     = self.x + self.w // 2
        self.cy     = self.y + self.h // 2

    def __getitem__(self, index):
        return self._blob[index]

# Global Variable
prev_error = 0
integral = 0
last_obj2_x = None   # Last known x-center of OBJ2 for identity persistence
last_obj3_x = None   # Last known x-center of OBJ3 for identity persistence
smoothed_boxes = [None] * MAX_OBJECTS

def compute_adaptive_threshold(img, base_threshold):
    """Shift LAB L-channel range based on current scene brightness so that
    yellow detection stays consistent across lighting conditions.
    A/B (chrominance) channels are kept stable; only L (luminance) is
    adjusted, with a small tolerance expansion in very dark scenes."""
    stats = img.get_statistics()
    avg_l = stats.l_mean()

    l_min, l_max, a_min, a_max, b_min, b_max = base_threshold

    # Shift L window proportionally to brightness deviation
    l_shift = (avg_l - REF_BRIGHTNESS) // 3
    new_l_min = max(0, l_min + l_shift)
    new_l_max = min(100, l_max + l_shift)

    # Widen chrominance tolerance in low-light (noisy) conditions
    if avg_l < 30:
        a_min -= 5
        a_max += 5
        b_min -= 5
        b_max += 5

    return (new_l_min, new_l_max, a_min, a_max, b_min, b_max), avg_l

def get_closest_rgb(lab_threshold):
    """ Calculate closest RGB color based on LAB threshold"""
    # 获取LAB空间的中心点值
    l_center = (lab_threshold[0] + lab_threshold[1]) // 2
    a_center = (lab_threshold[2] + lab_threshold[3]) // 2
    b_center = (lab_threshold[4] + lab_threshold[5]) // 2
    return image.lab_to_rgb((l_center,a_center,b_center))

def init_sensor():
    """ Initialize camera sensor"""
    sensor = Sensor()
    sensor.reset()
    sensor.set_framesize(width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
    sensor.set_pixformat(Sensor.RGB565)

    # Some sensors (for example gc2093_csi2) do not support all auto-control APIs.
    # Ignore unsupported controls so camera init can continue.
    for ctrl_name, ctrl_value in (
        ("set_auto_gain", True),
        ("set_auto_exposure", True),
        ("set_auto_whitebal", True),
    ):
        try:
            getattr(sensor, ctrl_name)(ctrl_value)
        except Exception as e:
            print(" {} not supported: {}".format(ctrl_name, e))

    return sensor

def init_display():
    """ Initialize display"""
    Display.init(Display.ST7701, to_ide=True)
    MediaManager.init()

def bbox_iou(box1, box2):
    """ Compute IoU between two boxes"""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    x_left = max(x1, x2)
    y_top = max(y1, y2)
    x_right = min(x1 + w1, x2 + w2)
    y_bottom = min(y1 + h1, y2 + h2)

    inter_w = max(0, x_right - x_left)
    inter_h = max(0, y_bottom - y_top)
    inter_area = inter_w * inter_h

    area1 = w1 * h1
    area2 = w2 * h2
    union_area = area1 + area2 - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area

def blob_confidence(blob):
    """ Confidence heuristic from area and fill ratio"""
    w, h = blob[2], blob[3]
    pixels = blob[4]
    rect_area = max(1, w * h)
    fill_ratio = pixels / rect_area
    return pixels * fill_ratio

def passes_second_filter(blob):
    """ Reject weak blobs by pixels and fill ratio"""
    w, h = blob[2], blob[3]
    pixels = blob[4]
    rect_area = max(1, w * h)
    fill_ratio = pixels / rect_area

    if pixels < MIN_BLOB_PIXELS:
        return False
    if fill_ratio < MIN_FILL_RATIO:
        return False
    return True

def select_distinct_top_blobs(blobs, max_objects=MAX_OBJECTS, iou_threshold=0.35):
    """ Select high-confidence non-duplicate blobs"""
    ranked = sorted(blobs, key=blob_confidence, reverse=True)
    selected = []

    for blob in ranked:
        box = blob[0:4]
        is_duplicate = False
        for picked in selected:
            if bbox_iou(box, picked[0:4]) > iou_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            selected.append(blob)
            if len(selected) >= max_objects:
                break

    return selected

def assign_objects(blobs):
    """Assign roles to detected blobs:
    OBJ1 = widest blob
    OBJ2 = leftmost of remaining two (left when all 3 present)
    OBJ3 = rightmost of remaining two (right when all 3 present)
    When only 1 'other' blob is found, its identity is preserved by
    comparing its position to the last known OBJ2/OBJ3 x-centers.
    Returns a 3-element list where a missing object is represented as None."""
    global last_obj2_x, last_obj3_x

    if not blobs:
        return blobs

    # OBJ1: blob with maximum width
    obj1 = max(blobs, key=lambda b: b[2])
    remaining = [b for b in blobs if b is not obj1]

    if len(remaining) == 2:
        # Normal 3-object case: left -> OBJ2, right -> OBJ3
        remaining.sort(key=lambda b: b[0] + b[2] // 2)
        obj2, obj3 = remaining[0], remaining[1]
        last_obj2_x = obj2[0] + obj2[2] // 2
        last_obj3_x = obj3[0] + obj3[2] // 2
        return [BlobObj(obj1), BlobObj(obj2), BlobObj(obj3)]

    elif len(remaining) == 1:
        other = remaining[0]
        other_x = other[0] + other[2] // 2
        if last_obj2_x is not None and last_obj3_x is not None:
            # Identify by proximity to last known positions
            dist2 = abs(other_x - last_obj2_x)
            dist3 = abs(other_x - last_obj3_x)
            if dist2 <= dist3:
                return [BlobObj(obj1), BlobObj(other), None]   # OBJ2 survives, OBJ3 absent
            else:
                return [BlobObj(obj1), None, BlobObj(other)]   # OBJ3 survives, OBJ2 absent
        else:
            # No history yet: fall back to positional (left=OBJ2, right=OBJ3)
            return [BlobObj(obj1), BlobObj(other), None]

    else:
        return [BlobObj(obj1)]

def unpack_objects(objects):
    """Pad tracked objects so OBJ1/OBJ2/OBJ3 can be unpacked safely."""
    padded = list(objects[:MAX_OBJECTS])
    while len(padded) < MAX_OBJECTS:
        padded.append(None)
    return padded[0], padded[1], padded[2]

def smooth_assigned_objects(objects, alpha=SMOOTH_ALPHA):
    """Apply simple exponential smoothing to object boxes to reduce frame jitter."""
    global smoothed_boxes

    stable = []
    padded = list(objects[:MAX_OBJECTS])
    while len(padded) < MAX_OBJECTS:
        padded.append(None)

    for idx, blob in enumerate(padded):
        if blob is None:
            smoothed_boxes[idx] = None
            stable.append(None)
            continue

        current = (blob[0], blob[1], blob[2], blob[3], blob[4])
        prev = smoothed_boxes[idx]

        if prev is None:
            smoothed = current
        else:
            smoothed = (
                int((1 - alpha) * prev[0] + alpha * current[0]),
                int((1 - alpha) * prev[1] + alpha * current[1]),
                int((1 - alpha) * prev[2] + alpha * current[2]),
                int((1 - alpha) * prev[3] + alpha * current[3]),
                int((1 - alpha) * prev[4] + alpha * current[4]),
            )

        smoothed_boxes[idx] = smoothed
        stable.append(BlobObj(smoothed))

    return stable

def protection_pattern_matches(obj1, obj2, obj3):
    """Validate the expected three-strip geometry for hand protection."""
    global TRIG_PROTECT

    #if obj1 is None or obj2 is None or obj3 is None:
    #    return True

    if obj1 is None and obj2 is None and obj3 is None:
        TRIG_PROTECT = False
        print("None Object detectted. Protection Feature is off")
        return True

    if obj1 is not None and obj1.h < MAX_TOP_H and obj2 is None and obj3 is None:
        TRIG_PROTECT = False
        print("Obj1 is getting smaller. Protection Feature is off")
        return True

    if (
        obj1 is not None
        and obj2 is not None
        and obj3 is not None
        and obj1.w >= MAX_TOP_W and obj1.h >= MAX_TOP_H
        and obj2.w >= MAX_SIDE_W and obj2.h >= MAX_SIDE_H
        and obj3.w >= MAX_SIDE_W and obj3.h >= MAX_SIDE_H
    ):
        TRIG_PROTECT = True
        print("Protection Feature is on")

    top_ok = obj1.w >= MAX_TOP_W and obj1.h >= MAX_TOP_H
    #left_ok = abs(obj2.w - MAX_SIDE_W) <= THRE_ERR_SIDE_W and abs(obj2.h - MAX_SIDE_H) <= THRE_ERR_SIDE_H
    #right_ok = abs(obj3.w - MAX_SIDE_W) <= THRE_ERR_SIDE_W and abs(obj3.h - MAX_SIDE_H) <= THRE_ERR_SIDE_H
    if obj2 is None and obj3 is None:
        sides_balanced = True
    elif obj2 is None or obj3 is None:
        sides_balanced = False
    elif obj2.w >= THRE_ERR_SIDE_W and obj3.w >= THRE_ERR_SIDE_W:
        sides_balanced = abs(obj2.w - obj3.w) <= THRE_ERR_SIDE_W and abs(obj2.h - obj3.h) <= THRE_ERR_SIDE_H
    else:
        sides_balanced = True
    #print(top_ok, sides_balanced)

    # A missing side strip while the top strip is still visible is treated as
    # an immediate protection condition.
    if obj1 is not None and ((obj2 is not None and obj3 is None) or (obj2 is None and obj3 is not None)):
        if obj2 is not None:
            if obj2.h > 20:
                sides_balanced = False
                print("obj2 is detected but obj3 is not detected")
            else:
                sides_balanced = True
        if obj3 is not None:
            if obj3.h > 20:
                sides_balanced = False
                print("obj3 is detected but obj2 is not detected")
            else:
                sides_balanced = True

    if top_ok == True:
        if sides_balanced == True:
            return True
        if obj2 is None and obj3 is None:
            return True

    elif top_ok == True and sides_balanced == False:
        print("side balance NO")
        return False
    elif top_ok == False and sides_balanced == True:
        print("Top NO")
        return False
    elif top_ok == False and sides_balanced == False:
        print("Side and Top all NO")
        return False

    #return top_ok and sides_balanced

def hand_protection_triggered(objects):
    """Arm protection once the expected pattern is seen, then stop on mismatch."""
    global TRIG_PROTECT

    obj1, obj2, obj3 = unpack_objects(objects)

    pattern_ok = protection_pattern_matches(obj1, obj2, obj3)

    if TRIG_PROTECT:
        return not pattern_ok
    else:
        return False

    #return not pattern_ok

def process_blobs(img, blobs, color, max_objects=1):
    """ Process multiple high-confidence distinct blobs"""
    if not blobs:
        return None, None, None

    # 二次过滤后再做去重和排序，避免同一目标被分裂或低质量框误检
    quality_blobs = [blob for blob in blobs if passes_second_filter(blob)]
    if not quality_blobs:
        return None, None, None

    # 选出高置信度且不重复的目标
    selected_blobs = select_distinct_top_blobs(quality_blobs, max_objects=max_objects)
    if not selected_blobs:
        return None, None, None

    # Reassign: OBJ1=widest, OBJ2=leftmost of rest, OBJ3=rightmost of rest
    selected_blobs = assign_objects(selected_blobs)
    selected_blobs = smooth_assigned_objects(selected_blobs)

    largest_blob = selected_blobs[0]
    target_x = SCREEN_CENTER
    current_x = largest_blob[0] + largest_blob[2] // 2

    # 绘制和输出多个目标，首个目标高亮
    for index, blob in enumerate(selected_blobs, start=1):
        if blob is None:
            continue
        x, y, w, h = blob[0], blob[1], blob[2], blob[3]
        stats = img.get_statistics(roi=blob[0:4])
        l_val = stats.l_mean()
        a_val = stats.a_mean()
        b_val = stats.b_mean()

        thickness = 4 if index == 1 else 2
        img.draw_rectangle(blob[0:4], color=color, thickness=thickness)
        img.draw_cross(x + w//2, y + h//2, color=color, thickness=2)

        if index == 2:
            # Draw obj2 labels to the left side of its shape to avoid overlapping obj1
            lx = max(0, x - 130)
            img.draw_string_advanced(lx, y,      16, f"Obj{index} W:{w} H:{h}", color=(0, 0, 0))
            img.draw_string_advanced(lx, y + 18, 16, f"L:{l_val} A:{a_val} B:{b_val}", color=(0, 255, 255))
            img.draw_string_advanced(lx, y + 36, 16, f"C:{blob_confidence(blob):.0f}", color=(255, 180, 0))
        elif index == 3:
            # Draw obj3 labels to the right side of its shape
            rx = x + w + 4
            img.draw_string_advanced(rx, y,      16, f"Obj{index} W:{w} H:{h}", color=(0, 0, 0))
            img.draw_string_advanced(rx, y + 18, 16, f"L:{l_val} A:{a_val} B:{b_val}", color=(0, 255, 255))
            img.draw_string_advanced(rx, y + 36, 16, f"C:{blob_confidence(blob):.0f}", color=(255, 180, 0))
        else:
            img.draw_string_advanced(x, y - 48, 16,
                                     f"Obj{index} W:{w} H:{h}", color=(0, 0, 0))
            img.draw_string_advanced(x, y - 24, 16,
                         f"L:{l_val} A:{a_val} B:{b_val}", color=(0, 255, 255))
            img.draw_string_advanced(x, y - 64, 16,
                         f"C:{blob_confidence(blob):.0f}", color=(255, 180, 0))

    # Draw target line and current position
    img.draw_line(SCREEN_CENTER, 0, SCREEN_CENTER, DISPLAY_HEIGHT, color=(0, 255, 0), thickness=1)
    img.draw_line(current_x, largest_blob[1], current_x, largest_blob[1] + largest_blob[3], color=(255, 0, 0), thickness=2)

    return selected_blobs

def draw_fps(img, fps):
    """绘制FPS信息 / Draw FPS information"""
    img.draw_string_advanced(0, 0, 20, f'FPS: {fps:.3f}', color=(255, 255, 255))

def read_touch():
    """Read current touch position. Returns (x, y) or None."""
    if _tp is None:
        return None
    try:
        pts = _tp.read()
        if pts and len(pts) > 0:
            p = pts[0]
            return (p[0], p[1])
    except:
        pass
    return None

def point_in_rect(px, py, rect):
    rx, ry, rw, rh = rect
    return rx <= px < rx + rw and ry <= py < ry + rh

def handle_touch_ui(tx, ty):
    """Process touch on input UI buttons. Returns True if a button was pressed."""
    global input_value, MAX_TOP_H, _touch_cooldown
    hit = False
    if point_in_rect(tx, ty, BTN_PLUS):
        input_value += 1
        hit = True
    elif point_in_rect(tx, ty, BTN_MINUS):
        input_value = max(1, input_value - 1)
        hit = True
    elif point_in_rect(tx, ty, BTN_OK):
        MAX_TOP_H = input_value
        print("MAX_TOP_H updated to {}".format(MAX_TOP_H))
        hit = True
    if hit:
        _touch_cooldown = TOUCH_COOLDOWN
    return hit

def process_touch():
    """Read touch, handle cooldown, and process button presses each frame."""
    global _touch_cooldown
    if _touch_cooldown > 0:
        _touch_cooldown -= 1
        return
    touch = read_touch()
    if touch:
        handle_touch_ui(touch[0], touch[1])

def draw_input_ui(img, value):
    """Draw MAX_TOP_H input box with +/- and OK buttons (upper-right)."""
    img.draw_string_advanced(UI_LABEL_X, UI_LABEL_Y, 16, "MAX_TOP_H", color=(255, 255, 255))
    img.draw_rectangle(VAL_BOX, color=(0, 0, 0), fill=True)
    img.draw_rectangle(VAL_BOX, color=(255, 255, 255), thickness=1)
    img.draw_string_advanced(VAL_BOX[0] + 4, VAL_BOX[1] + 4, 16, str(value), color=(0, 255, 0))
    img.draw_rectangle(BTN_PLUS, color=(0, 180, 0), fill=True)
    img.draw_string_advanced(BTN_PLUS[0] + 8, BTN_PLUS[1] + 4, 16, "+", color=(255, 255, 255))
    img.draw_rectangle(BTN_MINUS, color=(180, 0, 0), fill=True)
    img.draw_string_advanced(BTN_MINUS[0] + 8, BTN_MINUS[1] + 4, 16, "-", color=(255, 255, 255))
    img.draw_rectangle(BTN_OK, color=(0, 0, 180), fill=True)
    img.draw_string_advanced(BTN_OK[0] + 6, BTN_OK[1] + 4, 16, "OK", color=(255, 255, 255))

def draw_protection_alert(img):
    """Show a full-screen red protection warning on the camera output."""
    # Draw a red boundary around the full camera field of view.
    img.draw_rectangle((0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT), color=(255, 0, 0), thickness=4)
    # Show protection warning at the upper-left corner in red.
    img.draw_string_advanced(10, 10, 36, "protection", color=(255, 0, 0))

def protection_alarm_signal(sig):
    SIG_ALARM_1.value(sig)  # 检测人手时，GPIO输出低电平
    SIG_ALARM_2.value(not sig)  # 检测人手时，GPIO输出高电平

def main():
    global TRIG_PROTECT
    display_ready = False
    media_ready = False
    sensor = None

    try:
        # Initialize devices
        sensor = init_sensor()
        init_display()
        display_ready = True
        media_ready = True
        sensor.run()

        clock = time.clock()

        #  Select color index to detect
        color_index = 0
        threshold = THRESHOLDS[color_index]
        detect_color = get_closest_rgb(threshold)

        while True:
            points = tp.read(1)

            SIG_SYSTEMON.value(1)  # 系统开启时，GPIO输出高电平
            clock.tick()
            img = sensor.snapshot()

            # Process touch input for on-screen MAX_TOP_H controls
            process_touch()

            # Compute brightness-adaptive threshold (replaces global histeq
            # which distorted chrominance and hurt color consistency)
            adaptive_thresh, scene_brightness = compute_adaptive_threshold(img, threshold)

            # Detect specified color
            blobs = img.find_blobs(
                [adaptive_thresh],
                roi=(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT),
                pixels_threshold=PIXELS_THRESHOLD,
                area_threshold=AREA_THRESHOLD,
                merge=MERGE_BLOBS,
                margin=MERGE_MARGIN
            )
            if blobs:
                objects = process_blobs(img, blobs, detect_color, max_objects=MAX_OBJECTS)
                if objects:
                    if hand_protection_triggered(objects):
                        draw_protection_alert(img)
                        protection_alarm_signal(True)
                    else:
                        protection_alarm_signal(False)
                else:
                    protection_alarm_signal(False)
            else:
                # If no yellow object is detected, send stop command
                protection_alarm_signal(False)

            fps = clock.fps()
            draw_fps(img, fps)

            # Show brightness and adaptive threshold for debugging
            img.draw_string_advanced(0, 22, 16,
                f"Bright:{scene_brightness} Thr:L({adaptive_thresh[0]}-{adaptive_thresh[1]})",
                color=(255, 255, 0))

            draw_input_ui(img, input_value)
            Display.show_image(img)
            time.sleep_ms(5)

    except KeyboardInterrupt as e:
        print(" User interrupted: ", e)
        SIG_SYSTEMON.value(0)  # 系统结束时，GPIO输出低电平
    except Exception as e:
        print(f" Error occurred: {e}")
        SIG_SYSTEMON.value(0)  # 系统结束时，GPIO输出低电平
    finally:
        if 'sensor' in locals() and isinstance(sensor, Sensor):
            sensor.stop()
        if display_ready:
            Display.deinit()
        if media_ready:
            MediaManager.deinit()
        SIG_SYSTEMON.value(0)  # 系统结束时，GPIO输出低电平

if __name__ == "__main__":
    main()
