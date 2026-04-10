import requests
from bs4 import BeautifulSoup
from datetime import datetime
from tqdm import tqdm
import sys

station_list = ['0900-基隆','0910-三坑','0920-八堵','0930-七堵','0940-百福','0950-五堵','0960-汐止','0970-汐科','0980-南港','0990-松山','1000-臺北','1010-萬華','1020-板橋','1030-浮洲','1040-樹林','1050-南樹林','1060-山佳','1070-鶯歌','1075-鳳鳴','1080-桃園','1090-內壢','1100-中壢','1110-埔心','1120-楊梅','1130-富岡','1140-新富','1150-北湖','1160-湖口','1170-新豐','1180-竹北','1190-北新竹','1191-千甲','1192-新莊','1193-竹中','1194-六家','1201-上員','1202-榮華','1203-竹東','1204-橫山','1205-九讚頭','1206-合興','1207-富貴','1208-內灣','1210-新竹','1220-三姓橋','1230-香山','1240-崎頂','1250-竹南','2110-談文','2120-大山','2130-後龍','2140-龍港','2150-白沙屯','2160-新埔','2170-通霄','2180-苑裡','2190-日南','2200-大甲','2210-臺中港','2220-清水','2230-沙鹿','2240-龍井','2250-大肚','2260-追分','3140-造橋','3150-豐富','3160-苗栗','3170-南勢','3180-銅鑼','3190-三義','3210-泰安','3220-后里','3230-豐原','3240-栗林','3250-潭子','3260-頭家厝','3270-松竹','3280-太原','3290-精武','3300-臺中','3310-五權','3320-大慶','3330-烏日','3340-新烏日','3350-成功','3360-彰化','3370-花壇','3380-大村','3390-員林','3400-永靖','3410-社頭','3420-田中','3430-二水','3431-源泉','3432-濁水','3433-龍泉','3434-集集','3435-水里','3436-車埕','3450-林內','3460-石榴','3470-斗六','3480-斗南','3490-石龜','4050-大林','4060-民雄','4070-嘉北','4080-嘉義','4090-水上','4100-南靖','4110-後壁','4120-新營','4130-柳營','4140-林鳳營','4150-隆田','4160-拔林','4170-善化','4180-南科','4190-新市','4200-永康','4210-大橋','4220-臺南','4250-保安','4260-仁德','4270-中洲','4271-長榮大學','4272-沙崙','4290-大湖','4300-路竹','4310-岡山','4320-橋頭','4330-楠梓','4340-新左營','4350-左營','4360-內惟','4370-美術館','4380-鼓山','4390-三塊厝','4400-高雄','4410-民族','4420-科工館','4430-正義','4440-鳳山','4450-後庄','4460-九曲堂','4470-六塊厝','5000-屏東','5010-歸來','5020-麟洛','5030-西勢','5040-竹田','5050-潮州','5060-崁頂','5070-南州','5080-鎮安','5090-林邊','5100-佳冬','5110-東海','5120-枋寮','5130-加祿','5140-內獅','5160-枋山','5190-大武','5200-瀧溪','5210-金崙','5220-太麻里','5230-知本','5240-康樂','6000-臺東','6010-山里','6020-鹿野','6030-瑞源','6040-瑞和','6050-關山','6060-海端','6070-池上','6080-富里','6090-東竹','6100-東里','6110-玉里','6120-三民','6130-瑞穗','6140-富源','6150-大富','6160-光復','6170-萬榮','6180-鳳林','6190-南平','6200-林榮新光','6210-豐田','6220-壽豐','6230-平和','6240-志學','6250-吉安','7000-花蓮','7010-北埔','7020-景美','7030-新城','7040-崇德','7050-和仁','7060-和平','7070-漢本','7080-武塔','7090-南澳','7100-東澳','7110-永樂','7120-蘇澳','7130-蘇澳新','7150-冬山','7160-羅東','7170-中里','7180-二結','7190-宜蘭','7200-四城','7210-礁溪','7220-頂埔','7230-頭城','7240-外澳','7250-龜山','7260-大溪','7270-大里','7280-石城','7290-福隆','7300-貢寮','7310-雙溪','7320-牡丹','7330-三貂嶺','7331-大華','7332-十分','7333-望古','7334-嶺腳','7335-平溪','7336-菁桐','7350-猴硐','7360-瑞芳','7361-海科館','7362-八斗子','7380-四腳亭','7390-暖暖']
train_list = set()
try:
    date = sys.argv[1]
except Exception:
    date = str(datetime.today())[:10].replace("-", "/")
print("fetching train list...")
for station in tqdm(station_list):
    url = f"https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybystationblank?rideDate={date}&station={station}"
    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    direc_list = [soup.find_all("tbody")[0], soup.find_all("tbody")[1]]
    for direction in direc_list:
        for train in direction.find_all("tr"):
            try:
                content = train.find_all("td")
                train_id = content[1].find("a").get_text()
                if "自強(3000)" in train_id:
                    train_list.add(("新自強", train_id[8:]))
                elif "區間快" in train_id or "普悠瑪" in train_id or "太魯閣" in train_id:
                    train_list.add((train_id[:3], train_id[3:]))
                else:
                    train_list.add((train_id[:2], train_id[2:]))
            except Exception:
                continue
train_list = list(train_list)
print("fetching train data...")
file = open(date.replace("/", "")+".json", "w", encoding="utf-8")
file.close()
file = open(date.replace("/", "")+".json", "a", encoding="utf-8")
file.write("[\n")
text = ""
for (train_type, train_number) in tqdm(train_list):
    if text != "":
        text += ", \n"
    file.write(text)
    url = f"https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytrainno?rideDate={date}&trainNo={train_number}"
    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")

    try:
        train_info = soup.find_all("tbody")[0].find_all("tr")[1].find_all("td")
        start = train_info[0].get_text().lstrip("\n").rstrip("\n").replace("\n", " ")
        end   = train_info[2].get_text().lstrip("\n").rstrip("\n").replace("\n", " ")
        via   = train_info[3].get_text().replace("\n", "")
        note  = train_info[4].get_text().replace("\n", "").replace("花東民眾實名優先購票班次，乘車時須準備登載個人身份證字號之證件。", "花東民眾優先購票。").replace("本班次不發售無座票，非持本班次車票旅客，請勿搭乘。", "不發售無座票。").replace("本列次不發售無座票，非持本班次車票旅客，請勿搭乘。", "不發售無座票。").replace("不發售無座票，非持本班次車票旅客，請勿搭乘。", "不發售無座票。").replace("第6節為騰雲座艙，為本公司公告指定不發售無座位車票之車廂，持當日當次騰雲座艙車票旅客始可搭乘。", "第6節為騰雲座艙。").replace("第6節騰雲座艙，為本公司公告指定不發售無座位車票之車廂，持當日當次騰雲座艙車票旅客始可搭乘。", "第6節為騰雲座艙。").replace("第6節為騰雲座艙，為本局公告指定不發售無座位車票之車廂，持當日當次騰雲座艙車票旅客始可搭乘。", "第6節為騰雲座艙。").replace(" ", "")
        img   = " ".join([i.get("title") for i in train_info[4].find_all("img")])
        if "每日行駛" in note:
            drive_days = "1234567"
        elif "民國" in note and "行駛" in note:
            drive_days = "0"
        elif "週五行" in note:
            drive_days = "5"
        elif "週六行" in note:
            drive_days = "6"
        elif "週日行" in note:
            drive_days = "7"
        elif "週一、六行" in note:
            drive_days = "16"
        elif "週五、六行" in note:
            drive_days = "56"
        elif "週五、日行" in note:
            drive_days = "57"
        elif "週六、日行" in note:
            drive_days = "67"
        elif "週五至日行" in note:
            drive_days = "567"
        elif "週一、六、日行" in note:
            drive_days = "167"
        elif "週六、日及例假日行" in note:
            drive_days = "678"
        elif "週六停" in note:
            drive_days = "123457"
        elif "週日停" in note:
            drive_days = "123456"
        elif "週五、六停" in note:
            drive_days = "12347"
        elif "週六、日停" in note:
            drive_days = "12345"
        elif "週五至日停" in note:
            drive_days = "1234"
        elif "週六、日及例假日停" in note:
            drive_days = "123459"
        
        info_text = '"info": {"start": "' + start + '", "end": "' + end + '", "via": "' + via + '", "drive": "' + drive_days + '", "note": "' + note + '", "img": "' + img + '"}'
        # print(info_text)
    except Exception:
        text = ""
        continue
    try:
        direction = soup.find_all("tbody")[1]
    except Exception:
        text = ""
        continue
    train_data = direction.find_all("tr")
    text = '{"train": "' + str(train_type) + '", "number": ' + str(train_number) + ', "data": ['
    train_station_list = []
    train_time_list = []
    for data in train_data:
        try:
            content = data.find_all("td")
            # print(content)
            train_station_list.append(content[0].get_text())
            arr_time, dep_time = content[1].get_text(), content[2].get_text()
            arr_time = int(arr_time[:2]) * 60 + int(arr_time[3:])
            dep_time = int(dep_time[:2]) * 60 + int(dep_time[3:])
            if arr_time < 720 and "跨日" in img:
                arr_time += 1440
            if dep_time < 720 and arr_time > 1320:
                dep_time += 1440
            if arr_time == dep_time:
                arr_time -= 0.5
                dep_time += 0.5
            train_time_list.append((arr_time, dep_time))
            text += '{"x": "' + content[0].get_text() + '", "y": ' + str(arr_time) + '}, ' + '{"x": "' + content[0].get_text() + '", "y": ' + str(dep_time) + '}, '
        except Exception:
            continue
    # file.write(f'"Train": {train_type}|{train_number}|{train_station_list}|{train_time_list}\n')
    text = text[:-2] + '], ' + info_text + '}'
text += "\n]"
file.write(text)
file.close()

