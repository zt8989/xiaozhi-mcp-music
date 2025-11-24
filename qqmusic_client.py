import time
import base64
import httpx
import json
import random
import re
import execjs
import string


class QQ_Music:
    def __init__(self):
        self._headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://y.qq.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
        self.headers_mobile = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36 Edg/123.0.0.0',
            'Referer': 'https://y.qq.com/',
        }
        with open("./main.js", 'r', encoding='utf-8') as f:
            self.js_code = f.read()
        self._cookies = {}

    def set_cookie(self, cookie):  # 网页Cookie转换到Python字典格式
        list_ret = {}
        cookie_list = cookie.split('; ')
        for item in cookie_list:
            parts = item.split('=')
            list_ret[parts[0]] = parts[1]
            if len(parts) == 3:
                list_ret[parts[0]] = parts[1] + '=' + parts[2]
        return list_ret

    def get_sign(self, data):  # QQMusic_Sign算法
        return execjs.compile(self.js_code).call("o", data)

    async def _request(self, method, url, **kwargs):
        method = method.upper()
        async with httpx.AsyncClient() as client:
            return await client.request(method, url, **kwargs)

    async def get_music_url(self, music_mid):  # 通过Mid获取音乐播放URL
        response = await self._request(
            'GET',
            f'https://i.y.qq.com/v8/playsong.html?songmid={music_mid}&_qmp=0',
            cookies=self._cookies,
            headers=self.headers_mobile,
        )
        if response.status_code != 200:
            return {}
        return json.loads(re.findall('__ssrFirstPageData__\\s=(.*?)</script>', response.text)[0])['songList'][0]['url']

    async def get_music_info(self, music_id):  # 通过音乐的ID获取歌曲信息
        uin = ''.join(random.sample('1234567890', 10))
        data = {"comm": {"cv": 4747474, "ct": 24, "format": "json", "inCharset": "utf-8", "outCharset": "utf-8",
                         "notice": 0, "platform": "yqq.json", "needNewCode": 1, "uin": uin,
                         "g_tk_new_20200303": 708550273, "g_tk": 708550273},
                "req_1": {"module": "music.trackInfo.UniformRuleCtrl", "method": "CgiGetTrackInfo",
                          "param": {"ids": [music_id], "types": [0]}}}
        response = await self._request(
            'GET',
            'https://u.y.qq.com/cgi-bin/musicu.fcg?data={}'.format(json.dumps(data)),
            headers=self._headers,
            cookies=self._cookies,
        )
        result = json.loads(response.text)
        if result['code'] == 500001:
            return 'Error'
        return result['req_1']['data']['tracks']

    async def get_album_info(self, album_mid):  # 获取专辑信息
        response = await self._request(
            'GET',
            f'https://i.y.qq.com/n2/m/share/details/album.html?ADTAG=ryqq.albumDetail&source=ydetail&albummid={album_mid}',
            cookies=self._cookies,
            headers=self.headers_mobile,
        )
        if response.status_code != 200:
            return {}
        return json.loads(re.findall('firstPageData\\s=(.*?)\n', response.text)[0])

    async def search_music(self, name, page, limit=20):  # 搜索歌曲,name歌曲名,limit返回数量
        response = await self._request(
            'GET',
            'https://shc.y.qq.com/soso/fcgi-bin/search_for_qq_cp?_=1657641526460&g_tk=1037878909&uin=1804681355&format=json&inCharset=utf-8&outCharset=utf-8&notice=0'
            '&platform=h5&needNewCode=1&w={}&zhidaqu=1&catZhida=1&t=0&flag=1&ie=utf-8&sem=1'
            '&aggr=0&perpage={}&n={}&p={}&remoteplace=txt.mqq.all'.format(name, limit, limit, page),
            headers=self._headers,
        )
        return response.json()['data']['song']['list']

    async def search_music_2(self, name, limit=20):  # 搜索歌曲,name歌曲名,limit返回数量
        data = json.dumps(
            {"comm": {"g_tk": 997034911, "uin": ''.join(random.sample(string.digits, 10)), "format": "json",
                       "inCharset": "utf-8",
                       "outCharset": "utf-8", "notice": 0, "platform": "h5", "needNewCode": 1, "ct": 23, "cv": 0},
             "req_0": {"method": "DoSearchForQQMusicDesktop", "module": "music.search.SearchCgiService",
                       "param": {"remoteplace": "txt.mqq.all",
                                 "searchid": "".join(random.sample(string.digits + string.digits, 18)),
                                 "search_type": 0,
                                 "query": name, "page_num": 1, "num_per_page": limit}}},
            ensure_ascii=False).encode('utf-8')
        response = await self._request(
            'POST',
            'https://u.y.qq.com/cgi-bin/musicu.fcg?_webcgikey=DoSearchForQQMusicDesktop&_={}'.format(
                int(round(time.time() * 1000))),
            headers={
                'Accept': '/',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
                'Referer': 'https://y.qq.com/',
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_3_1 like Mac OS X; zh-CN) AppleWebKit/537.51.1 '
                              '(KHTML, like Gecko) Mobile/17D50 UCBrowser/12.8.2.1268 Mobile AliApp(TUnionSDK/0.1.20.3) '
                              'UCBrowser/12.8.2.1268 Mobile AliApp(TUnionSDK/0.1.20.3)',
            },
            data=data,
        )
        return response.json()['req_0']['data']['body']['song']['list']

    async def get_playlist_info(self, playlist_id):  # 通过歌单ID获取歌单信息
        response = await self._request(
            'GET',
            f'https://y.qq.com/n/ryqq/playlist/{playlist_id}',
            headers=self._headers,
            cookies=self._cookies,
        )
        return json.loads(str(re.findall('window.__INITIAL_DATA__ =(.*?)</script>', response.text)[0]).replace('undefined', '"undefined"'))

    async def get_playlist_info_num(self, playlist_id, song_num):
        data = {
            "req_0": {
                "module": "srf_diss_info.DissInfoServer",
                "method": "CgiGetDiss",
                "param": {
                    "disstid": playlist_id,
                    "onlysonglist": 1,
                    "song_begin": song_num,
                    "song_num": 15
                }
            },
            "comm": {
                "g_tk": 865217452,
                "uin": ''.join(random.sample('1234567890', 10)),
                "format": "json",
                "platform": "h5"
            }
        }
        response = await self._request(
            'GET',
            'https://u.y.qq.com/cgi-bin/musicu.fcg?data={}'.format(json.dumps(data)),
            headers=self._headers,
            cookies=self._cookies,
        )
        resp = json.loads(response.text)
        if resp['code'] == 500001:
            return 'Error'
        return resp

    async def get_recommended_playlist(self):
        response = await self._request(
            'GET',
            'https://y.qq.com/n/ryqq/category',
            headers=self._headers,
            cookies=self._cookies,
        )
        return json.loads(str(re.findall('window.__INITIAL_DATA__ =(.*?)</script>', response.text)[0]).replace('undefined', '"undefined"'))

    async def get_lyrics(self, mid):
        response = await self._request(
            'GET',
            'https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg?_={}&format=json&loginUin={}&songmid={}'.format(
                time.time(), ''.join(random.sample('1234567890', 10)), mid),
            headers=self._headers,
            cookies=self._cookies,
        )
        return base64.b64decode(response.json()['lyric']).decode('utf-8')

    async def get_radio_info(self):
        response = await self._request(
            'GET',
            'https://y.qq.com/n/ryqq/radio',
            headers=self._headers,
            cookies=self._cookies,
        )
        return json.loads(str(re.findall('window.__INITIAL_DATA__ =(.*?)</script>', response.text)[0]).replace('undefined', '"undefined"'))

    async def get_toplist_music(self):
        response = await self._request(
            'GET',
            'https://i.y.qq.com/n2/m/share/details/toplist.html?ADTAG=ryqq.toplist&type=0&id=4',
            headers=self.headers,
        )
        return json.loads(re.compile('firstPageData\\s=(.*?)\n').findall(response.text)[0])

    async def get_mv_url(self, vid):
        data = {"comm": {"ct": 6, "cv": 0, "g_tk": 1366999994, "uin": ''.join(random.sample('1234567890', 10)),
                 "format": "json", "platform": "yqq"},
                "mvInfo": {"module": "video.VideoDataServer", "method": "get_video_info_batch",
                           "param": {"vidlist": [vid],
                                     "required": ["vid", "type", "sid", "cover_pic", "duration", "singers",
                                                  "new_switch_str", "video_pay", "hint", "code", "msg", "name", "desc",
                                                  "playcnt", "pubdate", "isfav", "fileid", "filesize", "pay",
                                                  "pay_info", "uploader_headurl", "uploader_nick", "uploader_uin",
                                                  "uploader_encuin"]}},
                "mvUrl": {"module": "music.stream.MvUrlProxy", "method": "GetMvUrls",
                          "param": {"vids": [vid], "request_type": 10003, "addrtype": 3, "format": 264}}}
        response = await self._request(
            'POST',
            'https://u.y.qq.com/cgi-bin/musicu.fcg',
            data=json.dumps(data),
            timeout=1,
            headers=self._headers,
        )
        return response.json()

    async def get_singer_album_info(self, mid):
        uin = ''.join(random.sample('1234567890', 10))
        data = {"req_0": {"module": "music.homepage.HomepageSrv", "method": "GetHomepageTabDetail",
                          "param": {"uin": uin, "singerMid": mid, "tabId": "album", "page": 0,
                                    "pageSize": 10, "order": 0}},
                "comm": {"g_tk": 1666686892, "uin": int(uin), "format": "json", "platform": "h5", "ct": 23}}
        response = await self._request(
            'GET',
            'https://u.y.qq.com/cgi-bin/musicu.fcg?data={}'.format(json.dumps(data)),
            headers=self._headers,
            cookies=self._cookies,
        )
        resp = response.json()
        if resp['code'] == 500001:
            return 'Error'
        return resp['req_0']['data']['list']

    async def get_Toplist_Info(self):
        data = {
            "comm": {
                "cv": 4747474,
                "ct": 24,
                "format": "json",
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "notice": 0,
                "platform": "yqq.json",
                "needNewCode": 1,
                "uin": 0,
                "g_tk_new_20200303": 5381,
                "g_tk": 5381
            },
            "req_1": {
                "module": "musicToplist.ToplistInfoServer",
                "method": "GetAll",
                "param": {}
            }
        }
        response = await self._request(
            'GET',
            'https://u.y.qq.com/cgi-bin/musics.fcg?_={}&sign={}'.format(int(time.time() * 1000), self.get_sign(data)),
            headers=self._headers,
            cookies=self._cookies,
            data=json.dumps(data, separators=(',', ':')),
        )
        return response.json()['req_1']

    @property
    def headers(self):
        return self._headers
