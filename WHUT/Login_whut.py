import time
import random
import requests
import uuid
import base64
import winreg


class NetConnect:
    def __init__(self):
        self.host = 'https://www.baidu.com/'
        self.headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36'}
        self.__path = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
        self.__INTERNET_SETTINGS = winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER,
                                                    self.__path, 0, winreg.KEY_ALL_ACCESS)

    def get_server_form_Win(self):
        """获取代理配置的ip和端口号"""
        ip, port = "", ""
        if self.is_open_proxy_form_Win():
            try:
                ip, port = winreg.QueryValueEx(self.__INTERNET_SETTINGS, "ProxyServer")[0].split(":")
                print("检测到代理信息：{}:{}".format(ip, port))
            except FileNotFoundError as err:
                print("没有找到代理信息：" + str(err))
            except Exception as err:
                print("有其他报错：" + str(err))
        else:
            print("系统没有开启代理")
        return f'{ip}:{port}'

    def is_open_proxy_form_Win(self):
        """判断是否开启了代理"""
        try:
            if winreg.QueryValueEx(self.__INTERNET_SETTINGS, "ProxyEnable")[0] == 1:
                return True
        except FileNotFoundError as err:
            print("没有找到代理信息：" + str(err))
        except Exception as err:
            print("有其他报错：" + str(err))
        return False

    def get_mac_address(self):
        mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
        return "-".join([mac[e:e + 2] for e in range(0, 11, 2)]).upper()

    def check_connect(self):
        print('开始检查网络连接！')
        try:
            if self.is_open_proxy_form_Win():
                response = requests.get(url=self.host, headers=self.headers, timeout=1,
                                        proxies={'http': f'http://{self.get_server_form_Win()}',
                                                 'https': f'http://{self.get_server_form_Win()}'})
            else:
                response = requests.get(url=self.host, headers=self.headers, timeout=1)
            if 199 < response.status_code < 300:
                print('网络已连接！')
                return True
        except Exception as e:
            print('校园网未登录！')
        return False

    def connect_whut(self):
        print('开始联网！')
        filename = 'config.txt'
        try:
            with open(filename, 'r', encoding='utf=8') as f:
                config = f.readlines()
            if not config:
                username = input('请输入账号：')
                password = input('请输入密码：')
            else:
                username = config[0].strip()
                password = config[1].strip()
        except:
            print('\n配置文件缺失，请填写账号密码后生成\n生成后在本程序相同目录将产生一个config.txt文件\n若下次不想手动输入账号密码，请勿删除！\n')
            username = input('请输入账号：')
            password = input('请输入密码：')
            password = '{B}' + str(base64.b64encode(password.encode('utf-8'))).split("'")[1]
            current_file_path = __file__
            current_file_path = current_file_path.split("/", -1)
            path = ''
            for i in range(0, len(current_file_path) - 1):
                path = path + current_file_path[i] + '/'
            with open(path + filename, 'w') as file_object:
                file_object.write(username + '\n')
                file_object.write(password + '\n')

        try:
            print('正在认证，请稍后！')
            s = requests.session()
            res1 = s.post(
                url="http://172.30.16.34/include/auth_action.php",
                headers={
                    "Accept": "*/*",
                    "Accept-Encoding": "gzip, deflate",
                    "Accept-Language": "zh-CN",
                    "Cache-Control": "no-cache",
                    "Connection": "Keep-Alive",
                    "Content-Length": "109",
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "Cookie": r"",
                    "Host": "172.30.16.34",
                    'Origin': 'http://172.30.16.34',
                    'X-Requested-With': 'XMLHttpRequest',
                    "Referer": "http://172.30.16.34/srun_portal_pc.php?ac_id=5&url=1.1.1.1",
                    "User-Agent": "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 10.0; WOW64; Trident/7.0; .NET4.0C; .NET4.0E; .NET CLR 2.0.50727; .NET CLR 3.0.30729; .NET CLR 3.5.30729; Tablet PC 2.0)",
                },
                data={
                    "ac_id": random.choice([0, 5]),  # 一般登陆不上改这里，ac_id会变
                    "action": "login",
                    "ajax": "1",
                    "nas_ip": '',
                    "username": username,
                    "password": password,
                    "save_me": "1",
                    "user_ip": '',
                    "user_mac": self.get_mac_address,
                }, )
            content = res1.content.decode()
            print('服务器返回信息：' + content + '\n')
            if ('login_ok' in content) or ('successful' in content):
                print('\n登陆成功')
        except Exception as e:
            print('网络异常，请检查是否连接校园网wifi或网线！')


if __name__ == '__main__':
    nc = NetConnect()
    if not nc.check_connect():
        nc.connect_whut()
        while not nc.check_connect():
            print('\n10秒后开始重新连接！')
            time.sleep(10)
            nc.connect_whut()
    print('\n本窗口将在10秒后自动关闭！')
    time.sleep(10)
