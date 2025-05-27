import datetime
import os
import queue
import sys
import time
from collections import defaultdict
from functools import wraps
from pathlib import Path
from typing import Any, Dict, Iterable, List, Union

from .fileutil import *
from .httputil import *
from .strutil import *
from .sqlutil import *
from .notifyutil import *
from .singleinstance import *
from .translateutil import *


class UniqueQueue(queue.Queue):
    def __init__(self, maxsize=0):
        super().__init__(maxsize)
        self.queue_set = set()

    def put(self, item, block=True, timeout=None):
        """
        一个对象重复put将会忽略
        """
        hash_item = item
        if isinstance(item, dict):
            hash_item = tuple(item.items())
        if hash_item not in self.queue_set:  # 如果元素不在队列中，则添加
            self.queue_set.add(hash_item)
            super().put(item, block, timeout)


def measure_time(func):
    """Measure and print the execution time of a function.
    记录函数执行时间"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"Function '{func.__name__}' executed in {execution_time:.4f} seconds")
        return result

    return wrapper


def unique_items(iterable: Iterable) -> list:
    """Return unique items from an iterable while preserving order.
    列表去重"""
    seen = set()
    return [x for x in iterable if x not in seen and not seen.add(x)]


def current_datetime():
    """Get the current date and time."""
    return datetime.datetime.now()


def format_datetime(dt: datetime, format: str = '%Y-%m-%d %H:%M:%S') -> str:
    """Format a datetime object as a string."""
    return dt.strftime(format)


def parse_datetime(date_string: str, format: str = '%Y-%m-%d %H:%M:%S') -> datetime:
    """Parse a datetime string into a datetime object."""
    return datetime.datetime.strptime(date_string, format)


def cut_list(obj, size):
    return [obj[i:i + size] for i in range(0, len(obj), size)]


def group_data(
        data: Iterable[Union[List[Any], Dict[str, Any]]],
        group_by: Union[int, str],
        remove_duplicates: bool = False
) -> Dict[Any, List[Union[List[Any], Dict[str, Any]]]]:
    """
    根据指定列进行分组，汇总每组数据，并可以选择是否去重。
    
    :param data: 要处理的数据列表，每个元素是一个可迭代对象（如列表、元组或字典）。
    :param group_by: 用于分组的列索引（整数）或键（字符串）。 
    :param remove_duplicates: 是否去重，默认为 False。
    
    :return: 返回一个字典，其中键是分组依据，值是分组后的数据列表（去重后的数据列表）。
    
    
    # 示例数据 1（按索引分组）
    
    data_1 = [
        ['apple', 'fruit', 'red'],
        ['banana', 'fruit', 'yellow'],
        ['carrot', 'vegetable', 'orange'],
        ['spinach', 'vegetable', 'green'],
        ['mango', 'fruit', 'green'],
        ['apple', 'fruit', 'red'],  # 重复数据
    ]

    # 示例数据 2（按字典键分组）
    
    data_2 = [
        {'name': 'apple', 'category': 'fruit', 'color': 'red'},
        {'name': 'banana', 'category': 'fruit', 'color': 'yellow'},
        {'name': 'carrot', 'category': 'vegetable', 'color': 'orange'},
        {'name': 'spinach', 'category': 'vegetable', 'color': 'green'},
        {'name': 'mango', 'category': 'fruit', 'color': 'green'},
        {'name': 'apple', 'category': 'fruit', 'color': 'red'},  # 重复数据
    ]

    # 使用示例 1：按最后一列分组，且去重
    
    grouped_data_1 = group_and_summary(data_1, group_by=-1, remove_duplicates=True)

    # 使用示例 2：按 'category' 键分组，且去重
    
    grouped_data_2 = group_and_summary(data_2, group_by='category', remove_duplicates=True)

    # 打印分组结果 1（按索引分组）
    
    print("按索引分组的结果：")
    for group, items in grouped_data_1.items():
        print(f"Group: {group}")
        for item in items:
            print(f"  {item}")

    """

    grouped = defaultdict(list)  # 使用 defaultdict 便于添加元素

    # 根据 group_by 类型进行处理
    for row in data:
        if not row:
            continue
        if isinstance(group_by, int):  # 按列索引分组
            group_key = row[group_by]
        elif isinstance(group_by, str) and isinstance(row, dict):  # 按字典键分组
            group_key = row.get(group_by)
        else:
            raise ValueError("group_by 参数类型不正确，请传入整数索引或字典键名")

        if remove_duplicates:
            # 去重处理：只将不重复的行加入该组
            if row not in grouped[group_key]:
                grouped[group_key].append(row)
        else:
            # 不去重，直接加入该组
            grouped[group_key].append(row)

    return dict(grouped)  # 返回标准的字典而不是 defaultdict


def get_resource_dir(basedir=None):
    if not basedir:
        basedir = sys._getframe(1).f_code.co_filename
    current_dir = getattr(sys, '_MEIPASS', os.path.dirname(basedir))

    while True:
        resource_folder = os.path.join(current_dir, "resource")

        if os.path.exists(resource_folder) and os.path.isdir(resource_folder):
            break

        # 到达根目录 (盘符根目录) 时停止搜索
        if len(current_dir) <= 3:
            break

        current_dir = os.path.abspath(os.path.join(current_dir, os.pardir))

    return resource_folder


def get_resource(filename):
    if Path(filename).exists():
        return filename
    resource_path = get_resource_dir(sys._getframe(1).f_code.co_filename) + "/" + filename
    if Path(resource_path).exists():
        return str(Path(resource_path).absolute())
    if Path('~/' + filename).expanduser().exists():
        return str(Path('~/' + filename).expanduser().absolute())
    return None

__all__ = [
    # --- 类 ---
    'UniqueQueue',

    # --- 装饰器 ---
    'measure_time',

    # --- 函数 ---
    'unique_items',
    'current_datetime',
    'format_datetime',
    'parse_datetime',
    'cut_list',
    'group_data',
    'get_resource_dir',
    'get_resource',
]