#!/usr/bin/env python3
# _*_ coding:utf-8 _*_

import base64
import hashlib
import hmac
import json
import os
import re
import smtplib
import threading
import time
import urllib.parse
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

from configobj import ConfigObj
import logging
from . import util

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()  # 默认输出到 sys.stderr
handler.setLevel(logging.INFO)  # 处理器也设置为 INFO
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)

req = util.requests_session()

# 通知服务
# from qinglong
push_config = {
    'HITOKOTO': False,  # 启用一言（随机句子）

    'BARK_PUSH': '',  # bark IP 或设备码，例：https://api.day.app/DxHcxxxxxRxxxxxxcm/
    'BARK_ARCHIVE': '',  # bark 推送是否存档
    'BARK_GROUP': '',  # bark 推送分组
    'BARK_SOUND': '',  # bark 推送声音
    'BARK_ICON': '',  # bark 推送图标
    'BARK_LEVEL': '',  # bark 推送时效性
    'BARK_URL': '',  # bark 推送跳转URL

    'CONSOLE': True,  # 控制台输出

    'DD_BOT_SECRET': '',  # 钉钉机器人的 DD_BOT_SECRET
    'DD_BOT_TOKEN': '',  # 钉钉机器人的 DD_BOT_TOKEN

    'FEISHU_KEY': '',  # 飞书机器人的 FEISHU_KEY
    'FEISHU_SECRET': '',  # 飞书机器人的签名校验密钥（可选）

    'GOBOT_URL': '',  # go-cqhttp
    # 推送到个人QQ：http://127.0.0.1/send_private_msg
    # 群：http://127.0.0.1/send_group_msg
    'GOBOT_QQ': '',  # go-cqhttp 的推送群或用户
    # GOBOT_URL 设置 /send_private_msg 时填入 user_id=个人QQ
    #               /send_group_msg   时填入 group_id=QQ群
    'GOBOT_TOKEN': '',  # go-cqhttp 的 access_token

    'GOTIFY_URL': '',  # gotify地址,如https://push.example.de:8080
    'GOTIFY_TOKEN': '',  # gotify的消息应用token
    'GOTIFY_PRIORITY': 0,  # 推送消息优先级,默认为0

    'IGOT_PUSH_KEY': '',  # iGot 聚合推送的 IGOT_PUSH_KEY

    'PUSH_KEY': '',  # server 酱的 PUSH_KEY，兼容旧版与 Turbo 版

    'DEER_KEY': '',  # PushDeer 的 PUSHDEER_KEY
    'DEER_URL': '',  # PushDeer 的 PUSHDEER_URL

    'CHAT_URL': '',  # synology chat url
    'CHAT_TOKEN': '',  # synology chat token

    'PUSH_PLUS_TOKEN': '',  # push+ 微信推送的用户令牌
    'PUSH_PLUS_USER': '',  # push+ 微信推送的群组编码

    'QMSG_KEY': '',  # qmsg 酱的 QMSG_KEY
    'QMSG_TYPE': '',  # qmsg 酱的 QMSG_TYPE

    'QYWX_ORIGIN': '',  # 企业微信代理地址

    'QYWX_AM': '',  # 企业微信应用

    'QYWX_KEY': '',  # 企业微信机器人

    'TG_BOT_TOKEN': '',  # tg 机器人的 TG_BOT_TOKEN，例：1407203283:AAG9rt-6RDaaX0HBLZQq0laNOh898iFYaRQ
    'TG_USER_ID': '',  # tg 机器人的 TG_USER_ID，例：1434078534
    'TG_API_HOST': '',  # tg 代理 api
    'TG_PROXY_AUTH': '',  # tg 代理认证参数
    'TG_PROXY_HOST': '',  # tg 机器人的 TG_PROXY_HOST
    'TG_PROXY_PORT': '',  # tg 机器人的 TG_PROXY_PORT

    'AIBOTK_KEY': '',  # 智能微秘书 个人中心的apikey 文档地址：http://wechat.aibotk.com/docs/about
    'AIBOTK_TYPE': '',  # 智能微秘书 发送目标 room 或 contact
    'AIBOTK_NAME': '',  # 智能微秘书  发送群名 或者好友昵称和type要对应好

    'SMTP_SERVER': '',  # SMTP 发送邮件服务器，形如 smtp.exmail.qq.com:465
    'SMTP_SSL': 'false',  # SMTP 发送邮件服务器是否使用 SSL，填写 true 或 false
    'SMTP_EMAIL': '',  # SMTP 收发件邮箱，通知将会由自己发给自己
    'SMTP_PASSWORD': '',  # SMTP 登录密码，也可能为特殊口令，视具体邮件服务商说明而定
    'SMTP_NAME': '',  # SMTP 收发件人姓名，可随意填写

    'PUSHME_KEY': '',  # PushMe 酱的 PUSHME_KEY

    'CHRONOCAT_QQ': '',  # qq号
    'CHRONOCAT_TOKEN': '',  # CHRONOCAT 的token
    'CHRONOCAT_URL': '',  # CHRONOCAT的url地址

    'WEBHOOK_URL': '',  # 自定义通知 请求地址
    'WEBHOOK_BODY': '',  # 自定义通知 请求体
    'WEBHOOK_HEADERS': '',  # 自定义通知 请求头
    'WEBHOOK_METHOD': '',  # 自定义通知 请求方法
    'WEBHOOK_CONTENT_TYPE': '',  # 自定义通知 content-type

    'XTUIS_KEY': '',  # 虾推啥
    'PIPEHUB_KEY': '',  # pipehub 机器人的 key
    'AIOPS_KEY': '',  # aiops 机器人的 key，发手机
    'SHOWDOC_KEY': '',  # SHOWDOC https://push.showdoc.com.cn/#/push
    'NOTIFYX_KEY': '',  # https://notifyx.cn/console/dashboard
}
notify_function = []

# 读取配置文件
config_path = util.get_resource('wtfconfig.ini')

if config_path and Path(config_path).exists():
    cfg = ConfigObj(config_path, encoding='UTF-8')

    if 'notify' in cfg:
        section = cfg['notify']
        for key, value in section.items():
            push_config[key] = value

# 读取 面板变量 或者 github action 运行变量
for k in push_config:
    if os.getenv(k):
        v = os.getenv(k)
        push_config[k] = v


def bark(title: str, content: str) -> None:
    """
    使用 bark 推送消息。
    """
    if not push_config.get("BARK_PUSH"):
        logger.error("bark 服务的 BARK_PUSH 未设置!!")
        raise ValueError("bark 服务的 BARK_PUSH 未设置!!")
    logger.debug("bark 服务启动")

    if push_config.get("BARK_PUSH").startswith("http"):
        url = f'{push_config.get("BARK_PUSH")}/{urllib.parse.quote_plus(title)}/{urllib.parse.quote_plus(content)}'
    else:
        url = f'https://api.day.app/{push_config.get("BARK_PUSH")}/{urllib.parse.quote_plus(title)}/{urllib.parse.quote_plus(content)}'

    bark_params = {
        "BARK_ARCHIVE": "isArchive",
        "BARK_GROUP": "group",
        "BARK_SOUND": "sound",
        "BARK_ICON": "icon",
        "BARK_LEVEL": "level",
        "BARK_URL": "url",
    }
    params = ""
    for pair in filter(
            lambda pairs: pairs[0].startswith("BARK_")
                          and pairs[0] != "BARK_PUSH"
                          and pairs[1]
                          and bark_params.get(pairs[0]),
            push_config.items(),
    ):
        params += f"{bark_params.get(pair[0])}={pair[1]}&"
    if params:
        url = url + "?" + params.rstrip("&")
    response = req.get(url).json()

    if response["code"] == 200:
        logger.debug("bark 推送成功！")
    else:
        logger.error("bark 推送失败！{}", response)


def console(title: str, content: str) -> None:
    """
    使用 控制台 推送消息。
    """
    print(f"{title}\n\n{content}")


def dingding_bot(title: str, content: str) -> None:
    """
    使用 钉钉机器人 推送消息。
    """
    if not push_config.get("DD_BOT_SECRET") or not push_config.get("DD_BOT_TOKEN"):
        logger.error("钉钉机器人 服务的 DD_BOT_SECRET 或者 DD_BOT_TOKEN 未设置!!")
        raise ValueError("钉钉机器人 服务的 DD_BOT_SECRET 或者 DD_BOT_TOKEN 未设置!!")
    logger.debug("钉钉机器人 服务启动")

    timestamp = str(round(time.time() * 1000))
    secret_enc = push_config.get("DD_BOT_SECRET").encode("utf-8")
    string_to_sign = "{}\n{}".format(timestamp, push_config.get("DD_BOT_SECRET"))
    string_to_sign_enc = string_to_sign.encode("utf-8")
    hmac_code = hmac.new(
        secret_enc, string_to_sign_enc, digestmod=hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    url = f'https://oapi.dingtalk.com/robot/send?access_token={push_config.get("DD_BOT_TOKEN")}&timestamp={timestamp}&sign={sign}'
    headers = {"Content-Type": "application/json;charset=utf-8"}
    data = {"msgtype": "text", "text": {"content": f"{title}\n\n{content}"}}
    response = req.post(
        url=url, data=json.dumps(data), headers=headers, timeout=15
    ).json()

    if not response["errcode"]:
        logger.debug("钉钉机器人 推送成功！")
    else:
        logger.error("钉钉机器人 推送失败！{}", response)


def feishu_bot(title: str, content: str):
    feishu_text(title + '\n\n' + content)


def feishu_text(content: str) -> None:
    """
    使用 飞书机器人 推送文本消息。 https://open.feishu.cn/community/articles/7271149634339422210
    """
    if not push_config.get("FEISHU_KEY"):
        logger.error("飞书 服务的 FEISHU_KEY 未设置!!")
        raise ValueError("飞书 服务的 FEISHU_KEY 未设置!!")
    logger.debug("飞书 服务启动")

    url = f'https://open.feishu.cn/open-apis/bot/v2/hook/{push_config.get("FEISHU_KEY")}'
    data = {"msg_type": "text", "content": {"text": content}}

    if push_config.get("FEISHU_SECRET"):
        timestamp = str(round(time.time()))
        string_to_sign = '{}\n{}'.format(timestamp, push_config.get("FEISHU_SECRET"))
        hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        data.update({
            'timestamp': timestamp,
            'sign': sign
        })

    response = req.post(url, json=data).json()

    if response.get("StatusCode") == 0:
        logger.debug("飞书 推送成功！")
    else:
        logger.error("飞书 推送失败！错误信息如下：\n{}", response)


def feishu_richtext(title: str, content: list) -> None:
    """
    使用 飞书机器人 推送富文本消息。 https://open.feishu.cn/community/articles/7271149634339422210
    content: [
        [
            {
                "tag": "text",
                "text": "你的小可爱上线了！"
            },
            {
                "tag": "a",
                "text": "点击查看",
                "href": "https://sspai.com/u/100gle/updates"
            }
        ]
    ]

    text：普通文本
    a：超链接
    at：@符号
    img：图片

    """
    if not push_config.get("FEISHU_KEY"):
        logger.error("飞书 服务的 FEISHU_KEY 未设置!!")
        raise ValueError("飞书 服务的 FEISHU_KEY 未设置!!")
    logger.debug("飞书 服务启动")

    url = f'https://open.feishu.cn/open-apis/bot/v2/hook/{push_config.get("FEISHU_KEY")}'
    data = {"msg_type": "post", "content": {"post": {"zh-CN": {"title": title, "content": content}}}}

    if push_config.get("FEISHU_SECRET"):
        timestamp = str(round(time.time()))
        string_to_sign = '{}\n{}'.format(timestamp, push_config.get("FEISHU_SECRET"))
        hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        data.update({
            'timestamp': timestamp,
            'sign': sign
        })

    response = req.post(url, json=data).json()

    if response.get("StatusCode") == 0:
        logger.debug("飞书 推送成功！")
    else:
        logger.error("飞书 推送失败！错误信息如下：\n", response)


def go_cqhttp(title: str, content: str) -> None:
    """
    使用 go_cqhttp 推送消息。
    """
    if not push_config.get("GOBOT_URL") or not push_config.get("GOBOT_QQ"):
        logger.error("go-cqhttp 服务的 GOBOT_URL 或 GOBOT_QQ 未设置!!")
        raise ValueError("go-cqhttp 服务的 GOBOT_URL 或 GOBOT_QQ 未设置!!")
    logger.debug("go-cqhttp 服务启动")

    url = f'{push_config.get("GOBOT_URL")}?access_token={push_config.get("GOBOT_TOKEN")}&{push_config.get("GOBOT_QQ")}&message=标题:{title}\n内容:{content}'
    response = req.get(url).json()

    if response["status"] == "ok":
        logger.debug("go-cqhttp 推送成功！")
    else:
        logger.error("go-cqhttp 推送失败！{}", response)


def gotify(title: str, content: str) -> None:
    """
    使用 gotify 推送消息。
    """
    if not push_config.get("GOTIFY_URL") or not push_config.get("GOTIFY_TOKEN"):
        logger.error("gotify 服务的 GOTIFY_URL 或 GOTIFY_TOKEN 未设置!!")
        raise ValueError("gotify 服务的 GOTIFY_URL 或 GOTIFY_TOKEN 未设置!!")
    logger.debug("gotify 服务启动")

    url = f'{push_config.get("GOTIFY_URL")}/message?token={push_config.get("GOTIFY_TOKEN")}'
    data = {
        "title": title,
        "message": content,
        "priority": push_config.get("GOTIFY_PRIORITY"),
    }
    response = req.post(url, data=data).json()

    if response.get("id"):
        logger.debug("gotify 推送成功！")
    else:
        logger.error("gotify 推送失败！{}", response)


def iGot(title: str, content: str) -> None:
    """
    使用 iGot 推送消息。
    """
    if not push_config.get("IGOT_PUSH_KEY"):
        logger.error("iGot 服务的 IGOT_PUSH_KEY 未设置!!")
        raise ValueError("iGot 服务的 IGOT_PUSH_KEY 未设置!!")
    logger.debug("iGot 服务启动")

    url = f'https://push.hellyw.com/{push_config.get("IGOT_PUSH_KEY")}'
    data = {"title": title, "content": content}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = req.post(url, data=data, headers=headers).json()

    if response["ret"] == 0:
        logger.debug("iGot 推送成功！")
    else:
        logger.error(f'iGot 推送失败！{response["errMsg"]}')


def serverJ(title: str, content: str) -> None:
    """
    通过 serverJ 推送消息。
    """
    if not push_config.get("PUSH_KEY"):
        logger.error("serverJ 服务的 PUSH_KEY 未设置!!")
        raise ValueError("serverJ 服务的 PUSH_KEY 未设置!!")
    logger.debug("serverJ 服务启动")

    data = {"text": title, "desp": content.replace("\n", "\n\n")}
    if push_config.get("PUSH_KEY").find("SCT") != -1:
        url = f'https://sctapi.ftqq.com/{push_config.get("PUSH_KEY")}.send'
    else:
        url = f'https://sc.ftqq.com/{push_config.get("PUSH_KEY")}.send'
    response = req.post(url, data=data).json()

    if response.get("errno") == 0 or response.get("code") == 0:
        logger.debug("serverJ 推送成功！")
    else:
        logger.error(f'serverJ 推送失败！错误码：{response["message"]}')


def pushdeer(title: str, content: str) -> None:
    """
    通过PushDeer 推送消息
    """
    if not push_config.get("DEER_KEY"):
        logger.error("PushDeer 服务的 DEER_KEY 未设置!!")
        raise ValueError("PushDeer 服务的 DEER_KEY 未设置!!")
    logger.debug("PushDeer 服务启动")
    data = {
        "text": title,
        "desp": content,
        "type": "markdown",
        "pushkey": push_config.get("DEER_KEY"),
    }
    url = "https://api2.pushdeer.com/message/push"
    if push_config.get("DEER_URL"):
        url = push_config.get("DEER_URL")

    response = req.post(url, data=data).json()

    if len(response.get("content").get("result")) > 0:
        logger.debug("PushDeer 推送成功！")
    else:
        logger.error("PushDeer 推送失败！错误信息：{}", response)


def chat(title: str, content: str) -> None:
    """
    通过Chat 推送消息
    """
    if not push_config.get("CHAT_URL") or not push_config.get("CHAT_TOKEN"):
        logger.error("chat 服务的 CHAT_URL或CHAT_TOKEN 未设置!!")
        raise ValueError("chat 服务的 CHAT_URL或CHAT_TOKEN 未设置!!")
    logger.debug("chat 服务启动")
    data = "payload=" + json.dumps({"text": title + "\n" + content})
    url = push_config.get("CHAT_URL") + push_config.get("CHAT_TOKEN")
    response = req.post(url, data=data)

    if response.status_code == 200:
        logger.debug("Chat 推送成功！")
    else:
        logger.error("Chat 推送失败！错误信息：{}", response)


def pushplus_bot(title: str, content: str) -> None:
    """
    通过 push+ 推送消息。
    """
    if not push_config.get("PUSH_PLUS_TOKEN"):
        logger.error("PUSHPLUS 服务的 PUSH_PLUS_TOKEN 未设置!!")
        raise ValueError("PUSHPLUS 服务的 PUSH_PLUS_TOKEN 未设置!!")
    logger.debug("PUSHPLUS 服务启动")

    url = "http://www.pushplus.plus/send"
    data = {
        "token": push_config.get("PUSH_PLUS_TOKEN"),
        "title": title,
        "content": content,
        "topic": push_config.get("PUSH_PLUS_USER"),
    }
    body = json.dumps(data).encode(encoding="utf-8")
    headers = {"Content-Type": "application/json"}
    response = req.post(url=url, data=body, headers=headers).json()

    if response["code"] == 200:
        logger.debug("PUSHPLUS 推送成功！")

    else:
        url_old = "http://pushplus.hxtrip.com/send"
        headers["Accept"] = "application/json"
        response = req.post(url=url_old, data=body, headers=headers).json()

        if response["code"] == 200:
            logger.debug("PUSHPLUS(hxtrip) 推送成功！")

        else:
            logger.error("PUSHPLUS 推送失败！")


def qmsg_bot(title: str, content: str) -> None:
    """
    使用 qmsg 推送消息。
    """
    if not push_config.get("QMSG_KEY") or not push_config.get("QMSG_TYPE"):
        logger.error("qmsg 的 QMSG_KEY 或者 QMSG_TYPE 未设置!!")
        raise ValueError("qmsg 的 QMSG_KEY 或者 QMSG_TYPE 未设置!!")
    logger.debug("qmsg 服务启动")

    url = f'https://qmsg.zendee.cn/{push_config.get("QMSG_TYPE")}/{push_config.get("QMSG_KEY")}'
    payload = {"msg": f'{title}\n\n{content.replace("----", "-")}'.encode("utf-8")}
    response = req.post(url=url, params=payload).json()

    if response["code"] == 0:
        logger.debug("qmsg 推送成功！")
    else:
        logger.error(f'qmsg 推送失败！{response["reason"]}')


def wecom_app(title: str, content: str) -> None:
    """
    通过 企业微信 APP 推送消息。
    """
    if not push_config.get("QYWX_AM"):
        logger.error("QYWX_AM 未设置!!")
        raise ValueError("QYWX_AM 未设置!!")
    if isinstance(push_config.get("QYWX_AM"), list):
        QYWX_AM_AY = push_config.get("QYWX_AM")
    else:
        QYWX_AM_AY = re.split(",", push_config.get("QYWX_AM"))
    if 4 < len(QYWX_AM_AY) > 5:
        logger.error("QYWX_AM 设置错误!!")
        raise ValueError("QYWX_AM 设置错误!!")
    logger.debug("企业微信 APP 服务启动")

    corpid = QYWX_AM_AY[0]
    corpsecret = QYWX_AM_AY[1]
    touser = QYWX_AM_AY[2]
    agentid = QYWX_AM_AY[3]
    try:
        media_id = QYWX_AM_AY[4]
    except IndexError:
        media_id = ""
    wx = WeCom(corpid, corpsecret, agentid)
    # 如果没有配置 media_id 默认就以 text 方式发送
    if not media_id:
        message = title + "\n\n" + content
        response = wx.send_text(message, touser)
    else:
        response = wx.send_mpnews(title, content, media_id, touser)

    if response == "ok":
        logger.debug("企业微信推送成功！")
    else:
        logger.error("企业微信推送失败！错误信息如下：\n{}", response)


class WeCom:
    def __init__(self, corpid, corpsecret, agentid):
        self.CORPID = corpid
        self.CORPSECRET = corpsecret
        self.AGENTID = agentid
        self.ORIGIN = "https://qyapi.weixin.qq.com"
        if push_config.get("QYWX_ORIGIN"):
            self.ORIGIN = push_config.get("QYWX_ORIGIN")

    def get_access_token(self):
        url = f"{self.ORIGIN}/cgi-bin/gettoken"
        values = {
            "corpid": self.CORPID,
            "corpsecret": self.CORPSECRET,
        }
        resp = req.post(url, params=values)
        data = resp.json()
        return data["access_token"]

    def send_text(self, message, touser="@all"):
        send_url = (
            f"{self.ORIGIN}/cgi-bin/message/send?access_token={self.get_access_token()}"
        )
        send_values = {
            "touser": touser,
            "msgtype": "text",
            "agentid": self.AGENTID,
            "text": {"content": message},
            "safe": "0",
        }
        send_msges = bytes(json.dumps(send_values), "utf-8")
        respone = req.post(send_url, send_msges)
        respone = respone.json()
        return respone["errmsg"]

    def send_mpnews(self, title, message, media_id, touser="@all"):
        send_url = (
            f"{self.ORIGIN}/cgi-bin/message/send?access_token={self.get_access_token()}"
        )
        send_values = {
            "touser": touser,
            "msgtype": "mpnews",
            "agentid": self.AGENTID,
            "mpnews": {
                "articles": [
                    {
                        "title": title,
                        "thumb_media_id": media_id,
                        "author": "Author",
                        "content_source_url": "",
                        "content": message.replace("\n", "<br/>"),
                        "digest": message,
                    }
                ]
            },
        }
        send_msges = bytes(json.dumps(send_values), "utf-8")
        respone = req.post(send_url, send_msges)
        respone = respone.json()
        return respone["errmsg"]


def wecom_bot(title: str, content: str) -> None:
    """
    通过 企业微信机器人 推送消息。
    """
    if not push_config.get("QYWX_KEY"):
        logger.error("企业微信机器人 服务的 QYWX_KEY 未设置!!")
        raise ValueError("企业微信机器人 服务的 QYWX_KEY 未设置!!")
    logger.debug("企业微信机器人服务启动")

    origin = "https://qyapi.weixin.qq.com"
    if push_config.get("QYWX_ORIGIN"):
        origin = push_config.get("QYWX_ORIGIN")

    url = f"{origin}/cgi-bin/webhook/send?key={push_config.get('QYWX_KEY')}"
    headers = {"Content-Type": "application/json;charset=utf-8"}
    data = {"msgtype": "text", "text": {"content": f"{title}\n\n{content}"}}
    response = req.post(
        url=url, data=json.dumps(data), headers=headers, timeout=15
    ).json()

    if response["errcode"] == 0:
        logger.debug("企业微信机器人推送成功！")
    else:
        logger.error("企业微信机器人推送失败！{}", response)


def telegram_bot(title: str, content: str) -> None:
    """
    使用 telegram 机器人 推送消息。
    """
    if not push_config.get("TG_BOT_TOKEN") or not push_config.get("TG_USER_ID"):
        logger.error("tg 服务的 bot_token 或者 user_id 未设置!!")
        raise ValueError("tg 服务的 bot_token 或者 user_id 未设置!!")
    logger.debug("tg 服务启动")

    if push_config.get("TG_API_HOST"):
        url = f"https://{push_config.get('TG_API_HOST')}/bot{push_config.get('TG_BOT_TOKEN')}/sendMessage"
    else:
        url = (
            f"https://api.telegram.org/bot{push_config.get('TG_BOT_TOKEN')}/sendMessage"
        )
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "chat_id": str(push_config.get("TG_USER_ID")),
        "text": f"{title}\n\n{content}",
        "disable_web_page_preview": "true",
    }
    proxies = None
    if push_config.get("TG_PROXY_HOST") and push_config.get("TG_PROXY_PORT"):
        if push_config.get("TG_PROXY_AUTH") is not None and "@" not in push_config.get(
                "TG_PROXY_HOST"
        ):
            push_config["TG_PROXY_HOST"] = (
                    push_config.get("TG_PROXY_AUTH")
                    + "@"
                    + push_config.get("TG_PROXY_HOST")
            )
        proxyStr = "http://{}:{}".format(
            push_config.get("TG_PROXY_HOST"), push_config.get("TG_PROXY_PORT")
        )
        proxies = {"http": proxyStr, "https": proxyStr}
    response = req.post(
        url=url, headers=headers, params=payload, proxies=proxies
    ).json()

    if response["ok"]:
        logger.debug("tg 推送成功！")
    else:
        logger.error("tg 推送失败！", response)


def aibotk(title: str, content: str) -> None:
    """
    使用 智能微秘书 推送消息。
    """
    if (
            not push_config.get("AIBOTK_KEY")
            or not push_config.get("AIBOTK_TYPE")
            or not push_config.get("AIBOTK_NAME")
    ):
        logger.error("智能微秘书 的 AIBOTK_KEY 或者 AIBOTK_TYPE 或者 AIBOTK_NAME 未设置!!")
        raise ValueError("智能微秘书 的 AIBOTK_KEY 或者 AIBOTK_TYPE 或者 AIBOTK_NAME 未设置!!")
    logger.debug("智能微秘书 服务启动")

    if push_config.get("AIBOTK_TYPE") == "room":
        url = "https://api-bot.aibotk.com/openapi/v1/chat/room"
        data = {
            "apiKey": push_config.get("AIBOTK_KEY"),
            "roomName": push_config.get("AIBOTK_NAME"),
            "message": {"type": 1, "content": f"【青龙快讯】\n\n{title}\n{content}"},
        }
    else:
        url = "https://api-bot.aibotk.com/openapi/v1/chat/contact"
        data = {
            "apiKey": push_config.get("AIBOTK_KEY"),
            "name": push_config.get("AIBOTK_NAME"),
            "message": {"type": 1, "content": f"【青龙快讯】\n\n{title}\n{content}"},
        }
    body = json.dumps(data).encode(encoding="utf-8")
    headers = {"Content-Type": "application/json"}
    response = req.post(url=url, data=body, headers=headers).json()
    logger.debug(response)
    if response["code"] == 0:
        logger.debug("智能微秘书 推送成功！")
    else:
        logger.error(f'智能微秘书 推送失败！{response["error"]}')


def smtp(title: str, content: str) -> None:
    """
    使用 SMTP 邮件 推送消息。
    """
    if (
            not push_config.get("SMTP_SERVER")
            or not push_config.get("SMTP_SSL")
            or not push_config.get("SMTP_EMAIL")
            or not push_config.get("SMTP_PASSWORD")
            or not push_config.get("SMTP_NAME")
    ):
        logger.error(
            "SMTP 邮件 的 SMTP_SERVER 或者 SMTP_SSL 或者 SMTP_EMAIL 或者 SMTP_PASSWORD 或者 SMTP_NAME 未设置!!"
        )
        raise ValueError(
            "SMTP 邮件 的 SMTP_SERVER 或者 SMTP_SSL 或者 SMTP_EMAIL 或者 SMTP_PASSWORD 或者 SMTP_NAME 未设置!!"
        )
    logger.debug("SMTP 邮件 服务启动")

    message = MIMEText(content, "plain", "utf-8")
    message["From"] = formataddr(
        (
            Header(push_config.get("SMTP_NAME"), "utf-8").encode(),
            push_config.get("SMTP_EMAIL"),
        )
    )
    message["To"] = formataddr(
        (
            Header(push_config.get("SMTP_NAME"), "utf-8").encode(),
            push_config.get("SMTP_EMAIL"),
        )
    )
    message["Subject"] = Header(title, "utf-8")

    try:
        smtp_server = (
            smtplib.SMTP_SSL(push_config.get("SMTP_SERVER"))
            if push_config.get("SMTP_SSL") == "true"
            else smtplib.SMTP(push_config.get("SMTP_SERVER"))
        )
        smtp_server.login(
            push_config.get("SMTP_EMAIL"), push_config.get("SMTP_PASSWORD")
        )
        smtp_server.sendmail(
            push_config.get("SMTP_EMAIL"),
            push_config.get("SMTP_EMAIL"),
            message.as_bytes(),
        )
        smtp_server.close()
        logger.debug("SMTP 邮件 推送成功！")
    except Exception as e:
        logger.error(f"SMTP 邮件 推送失败！{e}")


def pushme(title: str, content: str) -> None:
    """
    使用 PushMe 推送消息。
    """
    if not push_config.get("PUSHME_KEY"):
        logger.error("PushMe 服务的 PUSHME_KEY 未设置!!")
        raise ValueError("PushMe 服务的 PUSHME_KEY 未设置!!")
    logger.debug("PushMe 服务启动")

    url = f'https://push.i-i.me/?push_key={push_config.get("PUSHME_KEY")}'
    data = {
        "title": title,
        "content": content,
    }
    response = req.post(url, data=data)

    if response.status_code == 200 and response.text == "success":
        logger.debug("PushMe 推送成功！")
    else:
        logger.error(f"PushMe 推送失败！{response.status_code} {response.text}")


def pipehub(title: str, content: str) -> None:
    """
    使用 pipehub 推送消息。
    https://www.pipehub.net
    """
    if not push_config.get("PIPEHUB_KEY"):
        logger.error("pipehub 服务的 PIPEHUB_KEY 未设置!!")
        raise ValueError("pipehub 服务的 PIPEHUB_KEY 未设置!!")
    logger.debug("pipehub 服务启动")
    if title:
        content = f"{title}\n\n{content}"
    response = req.post(f'https://api.pipehub.net/send/{push_config.get("PIPEHUB_KEY")}', data=content.encode('utf-8'))
    if response.status_code == 200:
        logger.debug("pipehub 推送成功！")
    else:
        logger.error(f"pipehub 推送失败！{response.status_code} {response.text}")


def xtuis(title: str, content: str) -> None:
    """
    使用 xtuis 推送消息。
    https://wx.xtuis.cn
    """
    if not push_config.get("XTUIS_KEY"):
        logger.error("xtuis 服务的 XTUIS_KEY 未设置!!")
        raise ValueError("xtuis 服务的 XTUIS_KEY 未设置!!")
    logger.debug("xtuis 服务启动")
    response = req.post(f'https://wx.xtuis.cn/{push_config.get("XTUIS_KEY")}.send', data={
        "text": title,
        "desp": content,
    })
    if response.status_code == 200:
        logger.debug("xtuis 推送成功！")
    else:
        logger.error(f"xtuis 推送失败！{response.status_code} {response.text}")


def aiops_phone(title: str, content: str) -> None:
    """
    使用 aiops 推送消息。
    """
    if not push_config.get("AIOPS_KEY"):
        logger.error("aiops 服务的 AIOPS_KEY 未设置!!")
        raise ValueError("aiops 服务的 AIOPS_KEY 未设置!!")
    logger.debug("aiops 服务启动")
    import uuid
    response = req.post("http://api.aiops.com/alert/api/event", json={
        "app": push_config.get("AIOPS_KEY"),
        "eventId": uuid.uuid4().hex,
        "eventType": "trigger",
        "alarmContent": f"{title}\n\n{content}",
    })
    if response.status_code == 200:
        logger.debug("aiops 推送成功！")
    else:
        logger.error(f"aiops 推送失败！{response.status_code} {response.text}")


def showdoc(title: str, content: str) -> None:
    """
    使用 showdoc 推送消息。
    """
    if not push_config.get("SHOWDOC_KEY"):
        logger.error("showdoc 服务的 SHOWDOC_KEY 未设置!!")
        raise ValueError("showdoc 服务的 SHOWDOC_KEY 未设置!!")
    logger.debug("showdoc 服务启动")
    response = req.post("https://push.showdoc.com.cn/server/api/push/" + push_config.get("SHOWDOC_KEY"), json={
        "title": title,
        "content": content,
    })
    if response.status_code == 200:
        logger.debug("showdoc 推送成功！")
    else:
        logger.error(f"showdoc 推送失败！{response.status_code} {response.text}")


def notifyx(title: str, content: str, description=None) -> None:
    """
    使用 notifyx 推送消息。
    """
    if not push_config.get("NOTIFYX_KEY"):
        logger.error("notifyx 服务的 NOTIFYX_KEY 未设置!!")
        raise ValueError("notifyx 服务的 NOTIFYX_KEY 未设置!!")
    logger.debug("notifyx 服务启动")
    response = req.post("https://www.notifyx.cn/api/v1/send/" + push_config.get("NOTIFYX_KEY"), json={
        "title": title,
        "content": content,
        "description": description,
    })
    if response.status_code == 200:
        logger.debug("notifyx 推送成功！")
    else:
        logger.error(f"notifyx 推送失败！{response.status_code} {response.text}")


def chronocat(title: str, content: str) -> None:
    """
    使用 CHRONOCAT 推送消息。
    """
    if (
            not push_config.get("CHRONOCAT_URL")
            or not push_config.get("CHRONOCAT_QQ")
            or not push_config.get("CHRONOCAT_TOKEN")
    ):
        logger.error("CHRONOCAT 服务的 CHRONOCAT_URL 或 CHRONOCAT_QQ 未设置!!")
        raise ValueError("CHRONOCAT 服务的 CHRONOCAT_URL 或 CHRONOCAT_QQ 未设置!!")
    logger.debug("CHRONOCAT 服务启动")

    user_ids = re.findall(r"user_id=(\d+)", push_config.get("CHRONOCAT_QQ"))
    group_ids = re.findall(r"group_id=(\d+)", push_config.get("CHRONOCAT_QQ"))

    url = f'{push_config.get("CHRONOCAT_URL")}/api/message/send'
    headers = {
        "Content-Type": "application/json",
        "Authorization": f'Bearer {push_config.get("CHRONOCAT_TOKEN")}',
    }

    for chat_type, ids in [(1, user_ids), (2, group_ids)]:
        if not ids:
            continue
        for chat_id in ids:
            data = {
                "peer": {"chatType": chat_type, "peerUin": chat_id},
                "elements": [
                    {
                        "elementType": 1,
                        "textElement": {"content": f"{title}\n\n{content}"},
                    }
                ],
            }
            response = req.post(url, headers=headers, data=json.dumps(data))
            if response.status_code == 200:
                if chat_type == 1:
                    logger.debug(f"QQ个人消息:{ids}推送成功！")
                else:
                    logger.debug(f"QQ群消息:{ids}推送成功！")
            else:
                if chat_type == 1:
                    logger.error(f"QQ个人消息:{ids}推送失败！")
                else:
                    logger.error(f"QQ群消息:{ids}推送失败！")


def parse_headers(headers):
    if not headers:
        return {}

    parsed = {}
    lines = headers.split("\n")

    for line in lines:
        i = line.find(":")
        if i == -1:
            continue

        key = line[:i].strip().lower()
        val = line[i + 1:].strip()
        parsed[key] = parsed.get(key, "") + ", " + val if key in parsed else val

    return parsed


def parse_body(body, content_type):
    if not body:
        return ""

    parsed = {}
    lines = body.split("\n")

    for line in lines:
        i = line.find(":")
        if i == -1:
            continue

        key = line[:i].strip().lower()
        val = line[i + 1:].strip()

        if not key or key in parsed:
            continue

        try:
            json_value = json.loads(val)
            parsed[key] = json_value
        except:
            parsed[key] = val

    if content_type == "application/x-www-form-urlencoded":
        data = urllib.parse.urlencode(parsed, doseq=True)
        return data

    if content_type == "application/json":
        data = json.dumps(parsed)
        return data

    return parsed


def format_notify_content(url, body, title, content):
    if "$title" not in url and "$title" not in body:
        return {}

    formatted_url = url.replace("$title", urllib.parse.quote_plus(title)).replace(
        "$content", urllib.parse.quote_plus(content)
    )
    formatted_body = body.replace("$title", title).replace("$content", content)

    return formatted_url, formatted_body


def custom_notify(title: str, content: str) -> None:
    """
    通过 自定义通知 推送消息。
    """
    if not push_config.get("WEBHOOK_URL") or not push_config.get("WEBHOOK_METHOD"):
        logger.error("自定义通知的 WEBHOOK_URL 或 WEBHOOK_METHOD 未设置!!")
        raise ValueError("自定义通知的 WEBHOOK_URL 或 WEBHOOK_METHOD 未设置!!")
    logger.debug("自定义通知服务启动")

    WEBHOOK_URL = push_config.get("WEBHOOK_URL")
    WEBHOOK_METHOD = push_config.get("WEBHOOK_METHOD")
    WEBHOOK_CONTENT_TYPE = push_config.get("WEBHOOK_CONTENT_TYPE")
    WEBHOOK_BODY = push_config.get("WEBHOOK_BODY")
    WEBHOOK_HEADERS = push_config.get("WEBHOOK_HEADERS")

    formatUrl, formatBody = format_notify_content(
        WEBHOOK_URL, WEBHOOK_BODY, title, content
    )

    if not formatUrl and not formatBody:
        logger.debug("请求头或者请求体中必须包含 $title 和 $content")
        return

    headers = parse_headers(WEBHOOK_HEADERS)
    body = parse_body(formatBody, WEBHOOK_CONTENT_TYPE)
    response = req.request(
        method=WEBHOOK_METHOD, url=formatUrl, headers=headers, timeout=15, data=body
    )

    if response.status_code == 200:
        logger.debug("自定义通知推送成功！")
    else:
        logger.error(f"自定义通知推送失败！{response.status_code} {response.text}")


def one() -> str:
    """
    获取一条一言。
    :return:
    """
    url = "https://v1.hitokoto.cn/"
    res = req.get(url).json()
    return res["hitokoto"] + "    ----" + res["from"]


if push_config.get("BARK_PUSH"):
    notify_function.append(bark)
if push_config.get("CONSOLE"):
    notify_function.append(console)
if push_config.get("DD_BOT_TOKEN") and push_config.get("DD_BOT_SECRET"):
    notify_function.append(dingding_bot)
if push_config.get("FEISHU_KEY"):
    notify_function.append(feishu_bot)
if push_config.get("GOBOT_URL") and push_config.get("GOBOT_QQ"):
    notify_function.append(go_cqhttp)
if push_config.get("GOTIFY_URL") and push_config.get("GOTIFY_TOKEN"):
    notify_function.append(gotify)
if push_config.get("IGOT_PUSH_KEY"):
    notify_function.append(iGot)
if push_config.get("PUSH_KEY"):
    notify_function.append(serverJ)
if push_config.get("DEER_KEY"):
    notify_function.append(pushdeer)
if push_config.get("CHAT_URL") and push_config.get("CHAT_TOKEN"):
    notify_function.append(chat)
if push_config.get("PUSH_PLUS_TOKEN"):
    notify_function.append(pushplus_bot)
if push_config.get("QMSG_KEY") and push_config.get("QMSG_TYPE"):
    notify_function.append(qmsg_bot)
if push_config.get("QYWX_AM"):
    notify_function.append(wecom_app)
if push_config.get("QYWX_KEY"):
    notify_function.append(wecom_bot)
if push_config.get("TG_BOT_TOKEN") and push_config.get("TG_USER_ID"):
    notify_function.append(telegram_bot)
if (
        push_config.get("AIBOTK_KEY")
        and push_config.get("AIBOTK_TYPE")
        and push_config.get("AIBOTK_NAME")
):
    notify_function.append(aibotk)
if (
        push_config.get("SMTP_SERVER")
        and push_config.get("SMTP_SSL")
        and push_config.get("SMTP_EMAIL")
        and push_config.get("SMTP_PASSWORD")
        and push_config.get("SMTP_NAME")
):
    notify_function.append(smtp)
if push_config.get("PUSHME_KEY"):
    notify_function.append(pushme)
if (
        push_config.get("CHRONOCAT_URL")
        and push_config.get("CHRONOCAT_QQ")
        and push_config.get("CHRONOCAT_TOKEN")
):
    notify_function.append(chronocat)
if push_config.get("WEBHOOK_URL") and push_config.get("WEBHOOK_METHOD"):
    notify_function.append(custom_notify)
if push_config.get("PIPEHUB_KEY"):
    notify_function.append(pipehub)
if push_config.get("XTUIS_KEY"):
    notify_function.append(xtuis)
if push_config.get("AIOPS_KEY"):
    notify_function.append(aiops_phone)
if push_config.get("SHOWDOC_KEY"):
    notify_function.append(showdoc)
if push_config.get("NOTIFYX_KEY"):
    notify_function.append(notifyx)


def send(title: str, content: str) -> None:
    if not content:
        logger.error(f"{title} 推送内容为空！")
        return

    # 根据标题跳过一些消息推送，环境变量：SKIP_PUSH_TITLE 用回车分隔
    skipTitle = os.getenv("SKIP_PUSH_TITLE")
    if skipTitle:
        if title in re.split("\n", skipTitle):
            logger.debug(f"{title} 在SKIP_PUSH_TITLE环境变量内，跳过推送！")
            return

    hitokoto = push_config.get("HITOKOTO")

    text = one() if hitokoto else ""
    content += "\n\n" + text

    ts = [
        threading.Thread(target=mode, args=(title, content), name=mode.__name__)
        for mode in notify_function
    ]
    [t.start() for t in ts]
    [t.join() for t in ts]


__all__ = [
    # 配置项
    'push_config',

    # 函数
    'bark',
    'console',
    'dingding_bot',
    'feishu_bot',
    'feishu_text',
    'feishu_richtext',
    'go_cqhttp',
    'gotify',
    'iGot',
    'serverJ',
    'pushdeer',
    'chat',
    'pushplus_bot',
    'qmsg_bot',
    'wecom_app',
    'WeCom',
    'wecom_bot',
    'telegram_bot',
    'aibotk',
    'smtp',
    'pushme',
    'pipehub',
    'xtuis',
    'aiops_phone',
    'showdoc',
    'notifyx',
    'chronocat',
    'custom_notify',
    'one',
    'send',
]


def main():
    send("title", "content")


if __name__ == "__main__":
    main()
