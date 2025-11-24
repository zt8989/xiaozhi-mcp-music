import json
import logging
import os
import time

import execjs
import httpx
from dotenv import load_dotenv

import qqmusic_client

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化QQ音乐对象
cookie_str = os.getenv('QQM_COOKIE')
if not cookie_str:
    raise RuntimeError("QQM_COOKIE must be set (export an env var or add it to .env)")

QQM = qqmusic_client.QQ_Music()
QQM._cookies = QQM.set_cookie(cookie_str)


def build_main_client(cookie=None):
    """Return a new qqmusic_client.QQ_Music bound to the configured cookie."""
    raw_cookie = cookie if cookie is not None else cookie_str
    client = qqmusic_client.QQ_Music()
    if raw_cookie:
        client._cookies = client.set_cookie(raw_cookie)
    return client


def build_service_client(cookie=None):
    """Instantiate the higher-level QQMusic helper bound to the cookie."""
    service_client = QQMusic()
    service_client.set_cookies(cookie if cookie is not None else cookie_str)
    return service_client

class QQMusic:
    def __init__(self):
        self.base_url = 'https://u.y.qq.com/cgi-bin/musicu.fcg'
        self.guid = '10000'
        self.uin = '0'
        self.cookies = {}
        self.headers = {
            "accept": "application/json",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "cache-control": "max-age=0",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Not(A:Brand\";v=\"99\", \"Microsoft Edge\";v=\"133\", \"Chromium\";v=\"133\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0",
            "Origin": "https://y.qq.com",
            "Referer": "https://y.qq.com/ryqq/css/common.092d215c4a601df90f9f.chunk.css?max_age=2592000",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0",
            "if-modified-since": "Tue, 04 Mar 2025 01:05:37 GMT",
            "referer": "https://y.qq.com/",
            "origin": "https://y.qq.com",
            "content-type": "application/x-www-form-urlencoded",
            "accept-charset": "utf-8",
            "content-type": "application/json; charset=utf-8"
        }  
        self.file_config = {
            'm4a': {'s': 'C400', 'e': '.m4a', 'bitrate': 'M4A'},
            '128': {'s': 'M500', 'e': '.mp3', 'bitrate': '128kbps'},
            '320': {'s': 'M800', 'e': '.mp3', 'bitrate': '320kbps'},
            'flac': {'s': 'F000', 'e': '.flac', 'bitrate': 'FLAC'},
        }

    async def _request(self, method, url, **kwargs):
        method = method.upper()
        async with httpx.AsyncClient() as client:
            return await client.request(method, url, **kwargs)

    def set_cookies(self, cookie_str):
        cookies = {}
        for cookie in cookie_str.split('; '):
            key, value = cookie.split('=', 1)
            cookies[key] = value
        self.cookies = cookies
        return cookies

    async def get_music_url(self, songmid, file_type='128'):
        """
        获取音乐播放URL

        参数:
        songmid: str - 歌曲的MID
        file_type: str - 音质类型，可选参数：'m4a', '128', '320', 'flac'

        返回:
        dict - 包含音乐播放URL和比特率的字典
        """
        if file_type not in self.file_config:
            raise ValueError("Invalid file_type. Choose from 'm4a', '128', '320', 'flac'")

        file_info = self.file_config[file_type]
        file = f"{file_info['s']}{songmid}{songmid}{file_info['e']}"

        req_data = {
            'req_1': {
                'module': 'vkey.GetVkeyServer',
                'method': 'CgiGetVkey',
                'param': {
                    'filename': [file],
                    'guid': self.guid,
                    'songmid': [songmid],
                    'songtype': [0],
                    'uin': self.uin,
                    'loginflag': 1,
                    'platform': '20',
                },
            },
            'loginUin': self.uin,
            'comm': {
                'uin': self.uin,
                'format': 'json',
                'ct': 24,
                'cv': 0,
            },
        }

        response = await self._request(
            'POST',
            self.base_url,
            json=req_data,
            cookies=self.cookies,
            headers=self.headers,
        )
        data = response.json()

        purl = data['req_1']['data']['midurlinfo'][0]['purl']
        if purl == '':
            # VIP
            return None

        url = data['req_1']['data']['sip'][0] + purl
        prefix = purl[:4]
        bitrate = next((info['bitrate'] for key, info in self.file_config.items() if info['s'] == prefix), '')

        return {'url': url, 'bitrate': bitrate}
    
    async def get_category_playlist(self, disstid, cookie):
        id = disstid
        ck = cookie
        # cookies = QQMusic.set_cookies(cookie_str)
        data = json.dumps({
            "comm":{
                "cv":4747474,
                "ct":24,
                "format":"json",
                "inCharset":"utf-8",
                "outCharset":"utf-8",
                "notice":0,
                "platform":"yqq.json",
                "needNewCode":1,
                "uin":ck['uin'],
                "g_tk_new_20200303":780715403,
                "g_tk":780715403
            },
            "req_2":{
                "module":"music.srfDissInfo.aiDissInfo",
                "method":"uniform_get_Dissinfo",
                "param":{
                    "disstid":int(id),
                    "userinfo":1,
                    "tag":1,
                    "orderlist":1,
                    "song_begin":0,
                    "song_num":1000,
                    "onlysonglist":0,
                    "enc_host_uin":""
                }
            }
        })

        with open("./loader.js", 'r', encoding="utf-8") as f:
            js_code = f.read()

        time_str = round(time.time() * 1000)
        sign = execjs.compile(js_code).call("get_sign",data)

        url = 'https://u6.y.qq.com/cgi-bin/musics.fcg'
        params = {
            '_': time_str,
            'sign': sign,
        }

        response = await self._request(
            'POST',
            url,
            headers=self.headers,
            data=data.encode(),
            cookies=ck,
            params=params,
        )
        # print(response.json)
        return response.json()['req_2']
    
    async def get_toplist_playlist(self, topid, cookie):
        id = topid
        ck = cookie
        data = json.dumps({
            "comm": {
                "cv": 4747474,
                "ct": 24,
                "format": "json",
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "notice": 0,
                "platform": "yqq.json",
                "needNewCode": 1,
                "uin": ck['uin'],
                "g_tk_new_20200303": 673978184,
                "g_tk": 673978184
            },
            "req_1": {
                "module": "musicToplist.ToplistInfoServer",
                "method": "GetDetail",
                "param": {
                    "topid": int(id),
                    "offset": 0,
                    "num": 100,
                    "period": ""
                }
            }
        })
        with open("./loader.js", 'r', encoding="utf-8") as f:
            js_code = f.read()

        time_str = round(time.time() * 1000)
        sign = execjs.compile(js_code).call("get_sign",data)
        print(sign)

        url = 'https://u6.y.qq.com/cgi-bin/musics.fcg'
        params = {
            '_': time_str,
            'sign': sign,
        }
        print(sign)

        response = await self._request(
            'POST',
            url,
            headers=self.headers,
            data=data.encode(),
            cookies=ck,
            params=params,
        )
        # print(response.json)
        return response.json()['req_1']
    
    async def get_comment(self, bizid, cookie, size):
        id = bizid
        ck = cookie
        pagesize = size
        data = json.dumps({
            "comm": {
                "cv": 4747474,
                "ct": 24,
                "format": "json",
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "notice": 0,
                "platform": "yqq.json",
                "needNewCode": 1,
                "uin": ck['uin'],
                "g_tk_new_20200303": 673978184,
                "g_tk": 673978184
            },
            "req_1": {
                "method": "GetCommentCount",
                "module": "music.globalComment.GlobalCommentRead",
                "param": {
                    "request_list": [
                        {
                            "biz_type": 1,
                            "biz_id": str(id),
                            "biz_sub_type": 0
                        }
                    ]
                }
            },
            "req_3": {
                "module": "music.globalComment.CommentRead",
                "method": "GetNewCommentList",
                "param": {
                    "BizType": 1,
                    "BizId":  str(id),
                    "LastCommentSeqNo": "",
                    "PageSize": int(pagesize),
                    "PageNum": 0,
                    "FromCommentId": "",
                    "WithHot": 1,
                    "PicEnable": 1,
                    "LastTotal": 0,
                    "LastTotalVer": "0"
                }
            },
            "req_4": {
                "module": "music.globalComment.CommentRead",
                "method": "GetHotCommentList",
                "param": {
                    "BizType": 1,
                    "BizId": str(id),
                    "LastCommentSeqNo": "",
                    "PageSize": int(pagesize),
                    "PageNum": 0,
                    "HotType": 2,
                    "WithAirborne": 1,
                    "PicEnable": 1
                }
            }
        })
        with open("./loader.js", 'r', encoding="utf-8") as f:
            js_code = f.read()

        time_str = round(time.time() * 1000)
        sign = execjs.compile(js_code).call("get_sign",data)
        print(sign)

        url = 'https://u6.y.qq.com/cgi-bin/musics.fcg'
        params = {
            '_': time_str,
            'sign': sign,
        }
        print(sign)

        response = await self._request(
            'POST',
            url,
            headers=self.headers,
            data=data.encode(),
            cookies=ck,
            params=params,
        )
        # print(response.json)
        return response.json()['req_3']
    
    async def get_user_songlist(self, id):
        headers = {
            "accept": "application/json",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "origin": "https://y.qq.com",
            "referer": "https://y.qq.com/portal/profile.html",
            "sec-ch-ua": "\"Not(A:Brand\";v=\"99\", \"Microsoft Edge\";v=\"133\", \"Chromium\";v=\"133\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0"
        }
        
        url = "https://c.y.qq.com/rsc/fcgi-bin/fcg_user_created_diss"
        params = {
            "hostUin": 0,
            "hostuin": id,
            "sin": 0,
            "size": 200,
            "g_tk": 5381,
            "loginUin": 0,
            "format": "json",
            "inCharset": "utf8",
            "outCharset": "utf-8",
            "notice": 0,
            "platform": "yqq.json",
            "needNewCode": 0
        }
        
        response = await self._request(
            'GET',
            url,
            headers=headers,
            params=params,
        )
        result = response.json()
        
        if result.get('code') == 4000:
            return {
                "result": 100,
                "data": {
                    "list": [],
                    "message": "这个人不公开歌单，需要他（她）的cookie"
                }
            }
        
        if not result.get('data'):
            return {
                "result": 200,
                "errMsg": "获取歌单出错"
            }
        
        disslist = result['data']['disslist']
        fav_diss = next((v for v in disslist if v.get('dirid') == 201), None)
        
        if fav_diss:
            fav_diss['diss_cover'] = 'http://y.gtimg.cn/mediastyle/global/img/cover_like.png'
        
        return {
            "result": 100,
            "data": {
                "list": disslist,
                "creator": {
                    "hostuin": id,
                    "encrypt_uin": result['data']['encrypt_uin'],
                    "hostname": result['data']['hostname']
                }
            }
        }
    
    async def get_user_collect_songlist(self, id, cookie): 
        t = round(time.time() * 1000)
        ck = cookie
        url = "https://c.y.qq.com/fav/fcgi-bin/fcg_get_profile_order_asset.fcg"
        params = {
            "_": t,
            "cv": "4747474",
            "ct": "20",
            "format": "json",
            "inCharset": "utf-8",
            "outCharset": "utf-8",
            "notice": "0",
            "platform": "yqq.json",
            "needNewCode": "1",
            "uin": ck['uin'],
            "g_tk_new_20200303": "379269186",
            "g_tk": "379269186",
            "cid": "205360956",
            "userid": id,
            "reqtype": "3",
            "sin": "0",
            "ein": "10"
        }
        
        response = await self._request(
            'GET',
            url,
            headers=self.headers,
            params=params,
            cookies=ck,
        )
        result = response.json()
        
        if not result.get('data'):
            return {
                "result": 500,
                "errMsg": "获取数据失败"
            }
        
        total_diss = result['data']['totaldiss']
        cdlist = result['data']['cdlist']
        
        return {
            "result": 100,
            "data": {
                "list": cdlist,
                "total": total_diss
            }
        }
        
async def get_song_qualities(songmid):
    """获取歌曲所有可用音质信息的辅助函数"""
    qqmusic = QQMusic()
    qqmusic.set_cookies(cookie_str)
    
    file_types = ['flac', '320', '128', 'm4a']
    results = {}
    
    for file_type in file_types:
        if result := await qqmusic.get_music_url(songmid, file_type):
            results[file_type] = result
    
    return {
        'available_qualities': list(results.keys()),
        'urls': results,
        'highest_quality': next((ft for ft in file_types if ft in results), None)
    }
