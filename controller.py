import os
import re
import subprocess
import time
from lxml import etree

def tap_by_desc(desc):
    node = find_by_desc(desc)
    if node:
        tap_by_bounds(node)

def find_by_desc(desc):
    os.system("adb shell uiautomator dump /sdcard/view.xml")
    os.system("adb pull /sdcard/view.xml >/dev/null")
    tree = etree.parse("view.xml")
    node = tree.xpath(f"//node[@content-desc='{desc}']")
    if not node:
        print(f"Element '{desc}' not found")
        return False
    else:    
        return node[0].get("bounds")

def tap_by_bounds(bounds):
    x, y = get_bounds_center(bounds)
    time.sleep(1)
    subprocess.run(["adb", "shell", "input", "tap", str(x), str(y)])
    print(f"Tapped at {x},{y}")

def get_bounds_center(bounds_str):
    nums = list(map(int, re.findall(r'\d+', bounds_str)))
    x = (nums[0] + nums[2]) // 2
    y = (nums[1] + nums[3]) // 2
    return x, y
