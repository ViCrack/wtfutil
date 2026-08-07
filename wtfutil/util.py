"""
杂项工具：去重队列、计时装饰器、时间、列表、分组、资源路径解析。
"""

import datetime
import queue
import sys
import threading
import time
from pathlib import Path
from collections import defaultdict
from functools import wraps
from typing import Any, Dict, Iterable, List, Union

from ._resource import find_resource_directory, resolve_resource_path

__all__ = [
    # data structures
    'UniqueQueue',
    # decorators
    'measure_time',
    # functions
    'unique_items',
    'current_datetime',
    'format_datetime',
    'parse_datetime',
    'cut_list',
    'group_data',
    'get_resource_dir',
    'get_resource',
]


class UniqueQueue(queue.Queue):
    """在整个队列生命周期内忽略重复值的 ``queue.Queue``。"""

    def __init__(self, maxsize: int = 0) -> None:
        super().__init__(maxsize)
        self.queue_set: set = set()
        self._deduplication_lock = threading.Lock()

    @staticmethod
    def _make_hashable(item: Any) -> Any:
        """递归转换常见容器，使内容等价的值可稳定去重。"""
        if isinstance(item, dict):
            return (
                "dict",
                frozenset(
                    (
                        UniqueQueue._make_hashable(key),
                        UniqueQueue._make_hashable(value),
                    )
                    for key, value in item.items()
                ),
            )
        if isinstance(item, (list, tuple)):
            return (
                type(item).__name__,
                tuple(UniqueQueue._make_hashable(value) for value in item),
            )
        if isinstance(item, (set, frozenset)):
            return (
                type(item).__name__,
                frozenset(UniqueQueue._make_hashable(value) for value in item),
            )
        hash(item)
        return item

    def put(self, item: Any, block: bool = True, timeout: float | None = None) -> None:
        hashable_item = self._make_hashable(item)
        with self._deduplication_lock:
            if hashable_item in self.queue_set:
                return
            super().put(item, block, timeout)
            self.queue_set.add(hashable_item)


def get_resource_dir(basedir: str | Path | None = None) -> str:
    """从指定路径或调用方脚本位置向上查找 ``resource`` 目录。"""
    anchor_path = basedir or sys._getframe(1).f_code.co_filename
    return str(find_resource_directory(anchor_path))


def get_resource(
    filename: str | Path,
    basedir: str | Path | None = None,
) -> str | None:
    """按当前路径、项目 ``resource`` 目录、用户家目录查找资源。"""
    anchor_path = basedir or sys._getframe(1).f_code.co_filename
    return resolve_resource_path(filename, anchor_path=anchor_path)


def measure_time(func):
    """打印被装饰函数的执行耗时（秒）。"""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        print(f"Function '{func.__name__}' executed in {execution_time:.4f} seconds")
        return result

    return wrapper


def unique_items(iterable: Iterable[Any]) -> list[Any]:
    """保序去重。"""
    seen: set = set()
    return [x for x in iterable if x not in seen and not seen.add(x)]


def current_datetime() -> datetime.datetime:
    """返回当前 datetime。"""
    return datetime.datetime.now()


def format_datetime(dt: datetime.datetime, format: str = '%Y-%m-%d %H:%M:%S') -> str:
    """格式化 datetime 为字符串。"""
    return dt.strftime(format)


def parse_datetime(date_string: str, format: str = '%Y-%m-%d %H:%M:%S') -> datetime.datetime:
    """解析时间字符串为 datetime。"""
    return datetime.datetime.strptime(date_string, format)


def cut_list(obj: list[Any], size: int) -> list[list[Any]]:
    """将列表按 size 切成二维列表。"""
    return [obj[i:i + size] for i in range(0, len(obj), size)]


def group_data(
        data: Iterable[Union[List[Any], Dict[str, Any]]],
        group_by: Union[int, str],
        remove_duplicates: bool = False,
) -> Dict[Any, List[Union[List[Any], Dict[str, Any]]]]:
    """
    按列索引（int）或 dict 键（str）分组，汇总每组数据，可选组内去重。

    :param data: 数据列表，每个元素为列表/元组或字典。
    :param group_by: 整数索引（按位置）或字符串键（按字典键）。
    :param remove_duplicates: 是否在组内去重，默认 False。
    :return: 以分组值为键、分组数据列表为值的字典。

    示例 1 — 按索引分组（列表行）：

        data = [
            ['apple',  'fruit',     'red'],
            ['banana', 'fruit',     'yellow'],
            ['carrot', 'vegetable', 'orange'],
            ['spinach','vegetable', 'green'],
            ['mango',  'fruit',     'green'],
            ['apple',  'fruit',     'red'],   # 重复
        ]
        grouped = group_data(data, group_by=1, remove_duplicates=True)
        # {'fruit': [['apple','fruit','red'],['banana','fruit','yellow'],['mango','fruit','green']],
        #  'vegetable': [['carrot','vegetable','orange'],['spinach','vegetable','green']]}

    示例 2 — 按字典键分组：

        data = [
            {'name': 'apple',  'category': 'fruit',     'color': 'red'},
            {'name': 'banana', 'category': 'fruit',     'color': 'yellow'},
            {'name': 'carrot', 'category': 'vegetable', 'color': 'orange'},
            {'name': 'apple',  'category': 'fruit',     'color': 'red'},   # 重复
        ]
        grouped = group_data(data, group_by='category', remove_duplicates=True)
        # {'fruit': [{'name':'apple',...},{'name':'banana',...}],
        #  'vegetable': [{'name':'carrot',...}]}
    """
    grouped: Dict[Any, list] = defaultdict(list)
    for row in data:
        if not row:
            continue
        if isinstance(group_by, int):
            group_key = row[group_by]
        elif isinstance(group_by, str) and isinstance(row, dict):
            group_key = row.get(group_by)
        else:
            raise ValueError("group_by 须为整数索引或字典键名")
        if remove_duplicates:
            if row not in grouped[group_key]:
                grouped[group_key].append(row)
        else:
            grouped[group_key].append(row)
    return dict(grouped)
