
const allStationDistances = {'基隆': -3.9, '三坑': -2.4, '八堵': 0, '七堵': 23, '百福': 50, '五堵': 80, '汐止': 94, '汐科': 107, '南港': 154, '松山': 182, '臺北': 246, '萬華': 274, '板橋': 318, '浮洲': 342, '樹林': 372, '南樹林': 392, '山佳': 411, '鶯歌': 455, '鳳鳴': 505, '桃園': 537, '內壢': 596, '中壢': 636, '埔心': 694, '楊梅': 734, '富岡': 802, '新富': 819, '北湖': 834, '湖口': 859, '新豐': 921, '竹北': 969, '北新竹': 1013, '千甲': 991, '新莊': 961, '竹中': 948, '六家': 917, '上員': 921, '榮華': 877, '竹東': 861, '橫山': 826, '九讚頭': 806, '合興': 784, '富貴': 770, '內灣': 748, '新竹': 1027, '三姓橋': 1075, '香山': 1107, '崎頂': 1169, '竹南': 1214, '談文': 1259, '大山': 1327, '後龍': 1364, '龍港': 1400, '白沙屯': 1481, '新埔': 1512, '通霄': 1570, '苑裡': 1631, '日南': 1708, '大甲': 1755, '臺中港': 1807, '清水': 1867, '沙鹿': 1899, '龍井': 1945, '大肚': 1995, '追分': 2045, '造橋': 1268, '豐富': 1327, '苗栗': 1367, '南勢': 1433, '銅鑼': 1475, '三義': 1549, '泰安': 1658, '后里': 1684, '豐原': 1751, '栗林': 1777, '潭子': 1802, '頭家厝': 1821, '松竹': 1838, '太原': 1856, '精武': 1873, '臺中': 1892, '五權': 1914, '大慶': 1935, '烏日': 1966, '新烏日': 1975, '成功': 1999, '彰化': 2070, '花壇': 2136, '大村': 2182, '員林': 2217, '永靖': 2252, '社頭': 2289, '田中': 2332, '二水': 2390, '源泉': 2420, '濁水': 2498, '龍泉': 2547, '集集': 2590, '水里': 2664, '車埕': 2686, '林內': 2471, '石榴': 2519, '斗六': 2567, '斗南': 2643, '石龜': 2682, '大林': 2728, '民雄': 2786, '嘉北': 2853, '嘉義': 2879, '水上': 2945, '南靖': 2971, '後壁': 3031, '新營': 3108, '柳營': 3141, '林鳳營': 3180, '隆田': 3235, '拔林': 3257, '善化': 3303, '南科': 3332, '新市': 3379, '永康': 3429, '大橋': 3466, '臺南': 3493, '保安': 3569, '仁德': 3583, '中洲': 3608, '長榮大學': 3634, '沙崙': 3665, '大湖': 3637, '路竹': 3667, '岡山': 3745, '橋頭': 3781, '楠梓': 3823, '新左營': 3874, '左營': 3894, '內惟': 3905, '美術館': 3922, '鼓山': 3934, '三塊厝': 3951, '高雄': 3960, '民族': 3973, '科工館': 3984, '正義': 4002, '鳳山': 4015, '後庄': 4054, '九曲堂': 4096, '六塊厝': 4146, '屏東': 4169, '歸來': 4195, '麟洛': 4218, '西勢': 4242, '竹田': 4279, '潮州': 4319, '崁頂': 4368, '南州': 4392, '鎮安': 4430, '林邊': 4461, '佳冬': 4500, '東海': 4531, '枋寮': 4572, '加祿': 4625, '內獅': 4660, '枋山': 4708, '大武': 5010, '瀧溪': 5127, '金崙': 5211, '太麻里': 5320, '知本': 5437, '康樂': 5508, '臺東': 5553, '山里': 5635, '鹿野': 5696, '瑞源': 5751, '瑞和': 5778, '關山': 5853, '海端': 5918, '池上': 5975, '富里': 6043, '東竹': 6104, '東里': 6164, '玉里': 6232, '三民': 6340, '瑞穗': 6434, '富源': 6525, '大富': 6557, '光復': 6632, '萬榮': 6688, '鳳林': 6737, '南平': 6779, '林榮新光': 6801, '豐田': 6863, '壽豐': 6891, '平和': 6909, '志學': 6939, '吉安': 7027, '花蓮': 7062, '北埔': 7108, '景美': 7173, '新城': 7226, '崇德': 7279, '和仁': 7379, '和平': 7458, '漢本': 7502, '武塔': 7631, '南澳': 7668, '東澳': 7748, '永樂': 7805, '蘇澳': 7824, '蘇澳新': 7857, '冬山': 7908, '羅東': 7958, '中里': 7976, '二結': 7988, '宜蘭': 8046, '四城': 8083, '礁溪': 8130, '頂埔': 8171, '頭城': 8193, '外澳': 8230, '龜山': 8265, '大溪': 8311, '大里': 8358, '石城': 8385, '福隆': 8439, '貢寮': 8477, '雙溪': 8530, '牡丹': 8564, '三貂嶺': 8599, '大華': 8563, '十分': 8535, '望古': 8518, '嶺腳': 8497, '平溪': 8487, '菁桐': 8470, '猴硐': 8624, '瑞芳': 8670, '海科館': 8713, '八斗子': 8717, '四腳亭': 8720, '暖暖': 8743};
const mountStationDistances = {'八堵': 0, '七堵': 23, '百福': 50, '五堵': 80, '汐止': 94, '汐科': 107, '南港': 154, '松山': 182, '臺北': 246, '萬華': 274, '板橋': 318, '浮洲': 342, '樹林': 372, '南樹林': 392, '山佳': 411, '鶯歌': 455, '鳳鳴': 505, '桃園': 537, '內壢': 596, '中壢': 636, '埔心': 694, '楊梅': 734, '富岡': 802, '新富': 819, '北湖': 834, '湖口': 859, '新豐': 921, '竹北': 969, '北新竹': 1013, '新竹': 1027, '三姓橋': 1075, '香山': 1107, '崎頂': 1169, '竹南': 1214, '造橋': 1268, '豐富': 1327, '苗栗': 1367, '南勢': 1433, '銅鑼': 1475, '三義': 1549, '泰安': 1658, '后里': 1684, '豐原': 1751, '栗林': 1777, '潭子': 1802, '頭家厝': 1821, '松竹': 1838, '太原': 1856, '精武': 1873, '臺中': 1892, '五權': 1914, '大慶': 1935, '烏日': 1966, '新烏日': 1975, '成功': 1999, '彰化': 2070, '花壇': 2136, '大村': 2182, '員林': 2217, '永靖': 2252, '社頭': 2289, '田中': 2332, '二水': 2390, '林內': 2471, '石榴': 2519, '斗六': 2567, '斗南': 2643, '石龜': 2682, '大林': 2728, '民雄': 2786, '嘉北': 2853, '嘉義': 2879, '水上': 2945, '南靖': 2971, '後壁': 3031, '新營': 3108, '柳營': 3141, '林鳳營': 3180, '隆田': 3235, '拔林': 3257, '善化': 3303, '南科': 3332, '新市': 3379, '永康': 3429, '大橋': 3466, '臺南': 3493, '保安': 3569, '仁德': 3583, '中洲': 3608, '大湖': 3637, '路竹': 3667, '岡山': 3745, '橋頭': 3781, '楠梓': 3823, '新左營': 3874, '左營': 3894, '內惟': 3905, '美術館': 3922, '鼓山': 3934, '三塊厝': 3951, '高雄': 3960, '民族': 3973, '科工館': 3984, '正義': 4002, '鳳山': 4015, '後庄': 4054, '九曲堂': 4096, '六塊厝': 4146, '屏東': 4169, '歸來': 4195, '麟洛': 4218, '西勢': 4242, '竹田': 4279, '潮州': 4319, '崁頂': 4368, '南州': 4392, '鎮安': 4430, '林邊': 4461, '佳冬': 4500, '東海': 4531, '枋寮': 4572, '加祿': 4625, '內獅': 4660, '枋山': 4708, '大武': 5010, '瀧溪': 5127, '金崙': 5211, '太麻里': 5320, '知本': 5437, '康樂': 5508, '臺東': 5553, '山里': 5635, '鹿野': 5696, '瑞源': 5751, '瑞和': 5778, '關山': 5853, '海端': 5918, '池上': 5975, '富里': 6043, '東竹': 6104, '東里': 6164, '玉里': 6232, '三民': 6340, '瑞穗': 6434, '富源': 6525, '大富': 6557, '光復': 6632, '萬榮': 6688, '鳳林': 6737, '南平': 6779, '林榮新光': 6801, '豐田': 6863, '壽豐': 6891, '平和': 6909, '志學': 6939, '吉安': 7027, '花蓮': 7062, '北埔': 7108, '景美': 7173, '新城': 7226, '崇德': 7279, '和仁': 7379, '和平': 7458, '漢本': 7502, '武塔': 7631, '南澳': 7668, '東澳': 7748, '永樂': 7805, '蘇澳新': 7857, '冬山': 7908, '羅東': 7958, '中里': 7976, '二結': 7988, '宜蘭': 8046, '四城': 8083, '礁溪': 8130, '頂埔': 8171, '頭城': 8193, '外澳': 8230, '龜山': 8265, '大溪': 8311, '大里': 8358, '石城': 8385, '福隆': 8439, '貢寮': 8477, '雙溪': 8530, '牡丹': 8564, '三貂嶺': 8599, '猴硐': 8624, '瑞芳': 8670, '四腳亭': 8720, '暖暖': 8743};
const seaStationDistances = {'八堵': 0, '七堵': 23, '百福': 50, '五堵': 80, '汐止': 94, '汐科': 107, '南港': 154, '松山': 182, '臺北': 246, '萬華': 274, '板橋': 318, '浮洲': 342, '樹林': 372, '南樹林': 392, '山佳': 411, '鶯歌': 455, '鳳鳴': 505, '桃園': 537, '內壢': 596, '中壢': 636, '埔心': 694, '楊梅': 734, '富岡': 802, '新富': 819, '北湖': 834, '湖口': 859, '新豐': 921, '竹北': 969, '北新竹': 1013, '新竹': 1027, '三姓橋': 1075, '香山': 1107, '崎頂': 1169, '竹南': 1214, '談文': 1259, '大山': 1327, '後龍': 1364, '龍港': 1400, '白沙屯': 1481, '新埔': 1512, '通霄': 1570, '苑裡': 1631, '日南': 1708, '大甲': 1755, '臺中港': 1807, '清水': 1867, '沙鹿': 1899, '龍井': 1945, '大肚': 1995, '追分': 2045, '彰化': 2117, '花壇': 2183, '大村': 2229, '員林': 2264, '永靖': 2299, '社頭': 2336, '田中': 2379, '二水': 2437, '林內': 2518, '石榴': 2566, '斗六': 2614, '斗南': 2690, '石龜': 2729, '大林': 2775, '民雄': 2833, '嘉北': 2900, '嘉義': 2926, '水上': 2992, '南靖': 3018, '後壁': 3078, '新營': 3155, '柳營': 3188, '林鳳營': 3227, '隆田': 3282, '拔林': 3304, '善化': 3350, '南科': 3379, '新市': 3426, '永康': 3476, '大橋': 3513, '臺南': 3540, '保安': 3616, '仁德': 3630, '中洲': 3655, '大湖': 3684, '路竹': 3714, '岡山': 3792, '橋頭': 3828, '楠梓': 3870, '新左營': 3921, '左營': 3941, '內惟': 3952, '美術館': 3969, '鼓山': 3981, '三塊厝': 3998, '高雄': 4007, '民族': 4020, '科工館': 4031, '正義': 4049, '鳳山': 4062, '後庄': 4101, '九曲堂': 4143, '六塊厝': 4193, '屏東': 4216, '歸來': 4242, '麟洛': 4265, '西勢': 4289, '竹田': 4326, '潮州': 4366, '崁頂': 4415, '南州': 4439, '鎮安': 4477, '林邊': 4508, '佳冬': 4547, '東海': 4578, '枋寮': 4619, '加祿': 4672, '內獅': 4707, '枋山': 4755, '大武': 5057, '瀧溪': 5174, '金崙': 5258, '太麻里': 5367, '知本': 5484, '康樂': 5555, '臺東': 5600, '山里': 5682, '鹿野': 5743, '瑞源': 5798, '瑞和': 5825, '關山': 5900, '海端': 5965, '池上': 6022, '富里': 6090, '東竹': 6151, '東里': 6211, '玉里': 6279, '三民': 6387, '瑞穗': 6481, '富源': 6572, '大富': 6604, '光復': 6679, '萬榮': 6735, '鳳林': 6784, '南平': 6826, '林榮新光': 6848, '豐田': 6910, '壽豐': 6938, '平和': 6956, '志學': 6986, '吉安': 7074, '花蓮': 7109, '北埔': 7155, '景美': 7220, '新城': 7273, '崇德': 7326, '和仁': 7426, '和平': 7505, '漢本': 7549, '武塔': 7678, '南澳': 7715, '東澳': 7795, '永樂': 7852, '蘇澳新': 7904, '冬山': 7955, '羅東': 8005, '中里': 8023, '二結': 8035, '宜蘭': 8093, '四城': 8130, '礁溪': 8177, '頂埔': 8218, '頭城': 8240, '外澳': 8277, '龜山': 8312, '大溪': 8358, '大里': 8405, '石城': 8432, '福隆': 8486, '貢寮': 8524, '雙溪': 8577, '牡丹': 8611, '三貂嶺': 8646, '猴硐': 8671, '瑞芳': 8717, '四腳亭': 8767, '暖暖': 8790};
const mainStationList = new Set(["基隆", "八堵", "七堵", "汐止", "南港", "松山", "臺北", "萬華", "板橋", "樹林", "鶯歌", "桃園", "中壢", "新竹", "竹南", "大甲", "臺中港", "沙鹿", "苗栗", "豐原", "臺中", "新烏日", "彰化", "員林", "田中", "二水", "斗六", "斗南", "嘉義", "新營", "隆田", "善化", "永康", "臺南", "中洲", "岡山", "楠梓", "新左營", "高雄", "鳳山", "屏東", "潮州", "枋寮", "臺東", "玉里", "花蓮", "新城", "和平", "東澳", "蘇澳新", "羅東", "宜蘭", "頭城", "雙溪", "瑞芳"]);
const mountStationList = new Set(['八堵', '七堵', '百福', '五堵', '汐止', '汐科', '南港', '松山', '臺北', '萬華', '板橋', '浮洲', '樹林', '南樹林', '山佳', '鶯歌', '鳳鳴', '桃園', '內壢', '中壢', '埔心', '楊梅', '富岡', '新富', '北湖', '湖口', '新豐', '竹北', '北新竹', '新竹', '三姓橋', '香山', '崎頂', '竹南', '造橋', '豐富', '苗栗', '南勢', '銅鑼', '三義', '泰安', '后里', '豐原', '栗林', '潭子', '頭家厝', '松竹', '太原', '精武', '臺中', '五權', '大慶', '烏日', '新烏日', '成功', '彰化', '花壇', '大村', '員林', '永靖', '社頭', '田中', '二水', '林內', '石榴', '斗六', '斗南', '石龜', '大林', '民雄', '嘉北', '嘉義', '水上', '南靖', '後壁', '新營', '柳營', '林鳳營', '隆田', '拔林', '善化', '南科', '新市', '永康', '大橋', '臺南', '保安', '仁德', '中洲', '大湖', '路竹', '岡山', '橋頭', '楠梓', '新左營', '左營', '內惟', '美術館', '鼓山', '三塊厝', '高雄', '民族', '科工館', '正義', '鳳山', '後庄', '九曲堂', '六塊厝', '屏東', '歸來', '麟洛', '西勢', '竹田', '潮州', '崁頂', '南州', '鎮安', '林邊', '佳冬', '東海', '枋寮', '加祿', '內獅', '枋山', '大武', '瀧溪', '金崙', '太麻里', '知本', '康樂', '臺東', '山里', '鹿野', '瑞源', '瑞和', '關山', '海端', '池上', '富里', '東竹', '東里', '玉里', '三民', '瑞穗', '富源', '大富', '光復', '萬榮', '鳳林', '南平', '林榮新光', '豐田', '壽豐', '平和', '志學', '吉安', '花蓮', '北埔', '景美', '新城', '崇德', '和仁', '和平', '漢本', '武塔', '南澳', '東澳', '永樂', '蘇澳新', '冬山', '羅東', '中里', '二結', '宜蘭', '四城', '礁溪', '頂埔', '頭城', '外澳', '龜山', '大溪', '大里', '石城', '福隆', '貢寮', '雙溪', '牡丹', '三貂嶺', '猴硐', '瑞芳', '四腳亭', '暖暖']);
const seaStationList = new Set(['八堵', '七堵', '百福', '五堵', '汐止', '汐科', '南港', '松山', '臺北', '萬華', '板橋', '浮洲', '樹林', '南樹林', '山佳', '鶯歌', '鳳鳴', '桃園', '內壢', '中壢', '埔心', '楊梅', '富岡', '新富', '北湖', '湖口', '新豐', '竹北', '北新竹', '新竹', '三姓橋', '香山', '崎頂', '竹南', "談文", "大山", "後龍", "龍港", "白沙屯", "新埔", "通霄", "苑裡", "日南", "大甲", "臺中港", "清水", "沙鹿", "龍井", "大肚", "追分", '彰化', '花壇', '大村', '員林', '永靖', '社頭', '田中', '二水', '林內', '石榴', '斗六', '斗南', '石龜', '大林', '民雄', '嘉北', '嘉義', '水上', '南靖', '後壁', '新營', '柳營', '林鳳營', '隆田', '拔林', '善化', '南科', '新市', '永康', '大橋', '臺南', '保安', '仁德', '中洲', '大湖', '路竹', '岡山', '橋頭', '楠梓', '新左營', '左營', '內惟', '美術館', '鼓山', '三塊厝', '高雄', '民族', '科工館', '正義', '鳳山', '後庄', '九曲堂', '六塊厝', '屏東', '歸來', '麟洛', '西勢', '竹田', '潮州', '崁頂', '南州', '鎮安', '林邊', '佳冬', '東海', '枋寮', '加祿', '內獅', '枋山', '大武', '瀧溪', '金崙', '太麻里', '知本', '康樂', '臺東', '山里', '鹿野', '瑞源', '瑞和', '關山', '海端', '池上', '富里', '東竹', '東里', '玉里', '三民', '瑞穗', '富源', '大富', '光復', '萬榮', '鳳林', '南平', '林榮新光', '豐田', '壽豐', '平和', '志學', '吉安', '花蓮', '北埔', '景美', '新城', '崇德', '和仁', '和平', '漢本', '武塔', '南澳', '東澳', '永樂', '蘇澳新', '冬山', '羅東', '中里', '二結', '宜蘭', '四城', '礁溪', '頂埔', '頭城', '外澳', '龜山', '大溪', '大里', '石城', '福隆', '貢寮', '雙溪', '牡丹', '三貂嶺', '猴硐', '瑞芳', '四腳亭', '暖暖']);


// 1. 定義真正的原始資料來源 (Raw Data)
const lightcolorPalette = {"普悠瑪": "#F12F2F", "太魯閣": "#F57C00", "新自強": "#7B1FA2", "自強": "#00994D", "莒光": "#FBC02D", "區間快": "#1A1AFF", "區間": "#262626"};
const darkcolorPalette  = {"普悠瑪": "#FF5252", "太魯閣": "#FF9800", "新自強": "#BB99FF", "自強": "#66FF6A", "莒光": "#FDD835", "區間快": "#33CCFF", "區間": "#E6E6E6"};

const _JP_LIGHT = {
    "特急ラピートα": "#0000B4", "特急ラピートβ": "#0000B4", "特急ラピート": "#0000B4",
    "特急サザン": "#00B400", "特急泉北ライナー": "#DAA520",
    "特急こうや": "#DC143C", "特急りんかん": "#DC143C", "特急": "#DC143C",
    "空港急行": "#FF4500", "急行": "#FF8C00", "快速急行": "#FF8C00", "区間急行": "#9ACD32",
    "準急": "#1E90FF", "各駅停車": "#969696", "普通": "#969696"
};
const _JP_DARK = {
    "特急ラピートα": "#4DA6FF", "特急ラピートβ": "#4DA6FF", "特急ラピート": "#4DA6FF",
    "特急サザン": "#00E676", "特急泉北ライナー": "#E0B0FF",
    "特急こうや": "#FF3D57", "特急りんかん": "#FF3D57", "特急": "#FF3D57",
    "空港急行": "#FF5722", "急行": "#FF9800", "快速急行": "#FF9800", "区間急行": "#8BC34A",
    "準急": "#4CAF50", "各駅停車": "#B0B0B0", "普通": "#B0B0B0"
};

// 2. 💡 黑魔法核心：讓原本的變數名「自動導航」到正確的顏色
const jpColorPalette    = new Proxy({}, { get: (_, prop) => isLight ? _JP_LIGHT[prop] : _JP_DARK[prop] });



// ==========================================
// 南海電鐵設定資料
// ==========================================



// ==========================================
// 全域變數狀態
// ==========================================
let currentRegion = null; 
let isLight = false;
let colorPalette = darkcolorPalette;
let deckInstance = null;
let realtime = false;
let rawData = [];
let yrawData = [];
let todaySegments = [];
let yesterdaySegments = [];
let isMountain = true;
let jpLinesStruct = {};

let state = {
    selectedLine: null, showSchedule: false, currentZoom: 0, 
    enabledTypes: new Set(),
    stationList: mountStationList, stationDistances: mountStationDistances, focusedStation: null,
    period: 8759, initialY: 246, currentTimeMinutes: 0,
    nankaiActiveLine: "南海本線", nankaiActiveDay: "平日"
};

let gridData = {
    denseLabels: [], normalLabels: [], sparseLabels: [], simpleLabels: [],
    thickLines: [], thinLines: [],
    denseLabelData: [], normalLabelData: [], sparseLabelData: [], mainLabelData: [],
    minDistance: 0, maxDistance: 0
};

// ==========================================
// 日期與 UI 服務設定
// ==========================================
const dateSelector = document.getElementById('date-selector');
let today = new Date();
if (today.getHours() < 2) { today.setDate(today.getDate() - 1); }
if (dateSelector) {
    dateSelector.value = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
}
today.setDate(today.getDate() - 1);

function getSelectedDateFilename() { 
    if(!dateSelector) return "";
    return realtime ? `Taiwan/data/${dateSelector.value.replace(/-/g, '')}_realtime.json` : `Taiwan/data/${dateSelector.value.replace(/-/g, '')}.json`; 
}
function getYesterdayFilename() { 
    if(!dateSelector) return "";
    const selectedDate = new Date(dateSelector.value + 'T00:00:00');
    selectedDate.setDate(selectedDate.getDate() - 1);
    const yesterdayDate = `${selectedDate.getFullYear()}-${String(selectedDate.getMonth() + 1).padStart(2, '0')}-${String(selectedDate.getDate()).padStart(2, '0')}`;
    return realtime ? `Taiwan/data/${yesterdayDate.replace(/-/g, '')}_realtime.json` : `Taiwan/data/${yesterdayDate.replace(/-/g, '')}.json`;
}

const serviceIcons = {
    "腳踏車設施": "https://www.railway.gov.tw/tra-tip-web/static/images/serve-bicy.png",
    "自由座": "https://www.railway.gov.tw/tra-tip-web/static/images/serve-freeSeat.jpg",
    "騰雲座艙": "https://www.railway.gov.tw/tra-tip-web/static/images/serve-business.svg",
    "親子車廂": "https://www.railway.gov.tw/tra-tip-web/static/images/serve-parenting.png",
    "哺乳室": "https://www.railway.gov.tw/tra-tip-web/static/images/serve-nursingroom.png",
    "輪椅座": "https://www.railway.gov.tw/tra-tip-web/static/images/serve-wheelchair.png",
    "訂便當服務": "https://www.railway.gov.tw/tra-tip-web/static/images/serve-lunchbox.png",
    "桌型座": "https://www.railway.gov.tw/tra-tip-web/static/images/serve-table.png",
    "跨日列車": "https://www.railway.gov.tw/tra-tip-web/static/images/serve-crossday.png"
};

const DOM = {
    infoBox: document.getElementById('info-content'),
    stationBox: document.getElementById('station-info-content'),
    valZoom: document.getElementById('val-zoom'),
    valX: document.getElementById('val-x'),
    valY: document.getElementById('val-y'),
    btnClearSelection: document.getElementById('btn-clear-selection'),
    viewMonitor: document.getElementById('view-monitor')
};

// ==========================================
// 系統初始化 (核心切換邏輯)
// ==========================================
window.initRegion = async function(region) {
    currentRegion = region;
    
    document.getElementById('startup-screen').style.display = 'none';
    document.getElementById('main-wrapper').style.display = 'flex';
    document.getElementById('sidebar').style.display = 'flex';
    document.getElementById('sidebar-toggle').style.display = 'block';
    
    const dynamicTypesContainer = document.getElementById('dynamic-type-pills');
    if(dynamicTypesContainer) dynamicTypesContainer.innerHTML = '';
    state.enabledTypes.clear();

    if (region === 'TW') {
        document.getElementById('controls-tw').style.display = 'block';
        if(document.getElementById('controls-jp')) document.getElementById('controls-jp').style.display = 'none';
        
        colorPalette = isLight ? lightcolorPalette : darkcolorPalette;
        if(dynamicTypesContainer) {
            Object.keys(colorPalette).forEach(type => {
                state.enabledTypes.add(type);
                dynamicTypesContainer.innerHTML += `<button class="pill active train-type-pill" data-type="${type}" style="background:${colorPalette[type]}; color:#fff">${type}</button>`;
            });
        }
        
        state.stationDistances = isMountain ? mountStationDistances : seaStationDistances;
        state.stationList = isMountain ? mountStationList : seaStationList;
        state.period = isMountain ? 8759 : 8806;

    } else if (region === 'JP') {
        document.getElementById('controls-tw').style.display = 'none';
        document.getElementById('controls-jp').style.display = 'block';
        colorPalette = jpColorPalette;

        // 💡 1. 從外部檔案讀取車站結構
        try {
            // 💡 修正路徑：拿掉 Japan/，直接抓 Nankai/All_Nankai_Distances_Nested.json
            const res = await fetch('Japan/Nankai/All_Nankai_Distances_Nested.json');

            // 💡 絕對只能呼叫一次 res.json()！
            const data = await res.json(); 
            
            // 把讀取到的資料指派給全域變數
            jpLinesStruct = data;
            window.jpLinesStruct = data;
        } catch (e) {
            console.error("無法載入 station.json:", e);
            window.jpLinesStruct = {}; // 防呆
        }
        
        const jpLineContainer = document.getElementById('jp-line-container');
        if(jpLineContainer) {
            jpLineContainer.innerHTML = '';
            // 💡 2. 使用剛剛 fetch 回來的 jpLinesStruct 來產生按鈕
            Object.keys(jpLinesStruct).forEach(line => {
                const isActive = line === state.nankaiActiveLine ? 'active' : '';
                const bg = isActive ? 'background:#E91E63; color:white' : '';
                jpLineContainer.innerHTML += `<button class="pill nankai-line-pill ${isActive}" data-line="${line}" style="${bg}">${line}</button>`;
            });
        }

        if(dynamicTypesContainer) {
            Object.keys(jpColorPalette).forEach(type => {
                state.enabledTypes.add(type);
                dynamicTypesContainer.innerHTML += `<button class="pill active train-type-pill" data-type="${type}" style="background:${jpColorPalette[type]}; color:#fff">${type}</button>`;
            });
        }

        // 💡 3. 確保 setupNankaiLine 也是使用新的結構
        setupNankaiLine(state.nankaiActiveLine);
    }
    
    bindDynamicPillEvents();
    await loadData();
    if (!deckInstance) initDeckGL();
};

// 新增一個通用的更新 ViewState 的函式
function updateOrbitBounds(maxDist) {
    if (!deckInstance) return;
    
    const newView = new deck.OrbitView({
        id: 'orbit-view',
        controller: true,
        // 💡 關鍵：將邊界設定為 0 到 maxDist + 一點緩衝 (例如 5km)
        // 這樣下方就不會出現多餘的空白網格
        bounds: [0, 0, 4680, maxDist + 5] 
    });

    deckInstance.setProps({ views: [newView] });
}

window.setupNankaiLine = function(lineName) {
    state.nankaiActiveLine = lineName;
    const rawLineData = window.jpLinesStruct[lineName] || {};
    
    // 💡 修正 1：設定 Y 軸放大倍率，讓 64 公里撐開到大約 1600 單位高
    const Y_SCALE = 25; 
    const scaledData = {};
    for (const [st, dist] of Object.entries(rawLineData)) {
        scaledData[st] = dist * Y_SCALE;
    }

    state.stationDistances = scaledData;
    state.stationList = new Set(Object.keys(scaledData));

    const dists = Object.values(scaledData);
    const maxDist = dists.length > 0 ? Math.max(...dists) : 0;
    state.period = maxDist;

    if (deckInstance) {
        // 💡 修正 2：換回純 2D 平面的 OrthographicView
        const newView = new deck.OrthographicView({
            id: 'ortho',
            controller: true
        });
        deckInstance.setProps({ views: [newView] });
        
        updateStationGridData();
        renderLayers();
    }
};

function bindDynamicPillEvents() {
    const container = document.getElementById('dynamic-type-pills');
    if(container) {
        container.onclick = (e) => {
            if (e.target.classList.contains('train-type-pill')) {
                const type = e.target.getAttribute('data-type');
                if (state.enabledTypes.has(type)) {
                    state.enabledTypes.delete(type);
                    e.target.style.background = 'transparent';
                    e.target.style.color = 'var(--text-color)';
                    if (state.selectedLine && state.selectedLine.train === type) {
                        state.selectedLine = null;
                        // 這裡原本有 updateInfoBox()，我們把它移到最下面統一執行
                    }
                } else {
                    state.enabledTypes.add(type);
                    e.target.style.background = colorPalette[type];
                    e.target.style.color = '#fff';
                }
                if (deckInstance) renderLayers();
                
                // 💡 1. 補在這裡！點擊單一車種後，讓下方看板立即更新
                updateInfoBox(); 
            }
        };
    }

    const twLineContainer = document.getElementById('tw-line-container');
    if (twLineContainer) {
        twLineContainer.onclick = (e) => {
            if (e.target.classList.contains('line-pill')) {
                document.querySelectorAll('#tw-line-container .line-pill').forEach(p => p.classList.remove('active'));
                e.target.classList.add('active');
                isMountain = e.target.getAttribute('data-line') === 'mountain';
                state.stationList = isMountain ? mountStationList : seaStationList;
                state.stationDistances = isMountain ? mountStationDistances : seaStationDistances;
                state.period = isMountain ? 8759 : 8806;
                
                if (state.selectedLine) {
                    const updatedMatch = rawData.find(t => t.number === state.selectedLine.number && t.data.some(p => state.stationList.has(p.x)));
                    const yupdatedMatch = yrawData.find(t => t.number === state.selectedLine.number && t.data.some(p => state.stationList.has(p.x)));
                    if (updatedMatch) state.selectedLine = updatedMatch;
                    else if (yupdatedMatch) state.selectedLine = yupdatedMatch;
                    else { state.selectedLine = null; state.showSchedule = false; }
                }
                updateStationGridData();
                if(deckInstance) renderLayers();
                updateInfoBox(); // (你原本這裡就有了，讚！)
            }
        };
    }

    const jpLineContainer = document.getElementById('jp-line-container');
    if (jpLineContainer) {
        jpLineContainer.onclick = (e) => {
            if (e.target.classList.contains('nankai-line-pill')) {
                document.querySelectorAll('#jp-line-container .nankai-line-pill').forEach(p => { p.classList.remove('active'); p.style.background = ''; p.style.color=''; });
                e.target.classList.add('active');
                e.target.style.background = '#E91E63'; e.target.style.color = 'white';
                setupNankaiLine(e.target.getAttribute('data-line'));
                centerCameraOnLine();
            }
        };
    }

    const jpDayContainer = document.getElementById('jp-day-container');
    if (jpDayContainer) {
        jpDayContainer.onclick = (e) => {
            if (e.target.classList.contains('day-pill')) {
                document.querySelectorAll('#jp-day-container .day-pill').forEach(p => { p.classList.remove('active'); p.style.background = ''; p.style.color=''; });
                e.target.classList.add('active');
                state.nankaiActiveDay = e.target.getAttribute('data-day');
                
                // ⚠️ 這裡順便幫你抓到一個小問題：把 nankaiActiveDay 同步給 dayType
                // 因為我們過濾器是用 state.dayType 判斷的！
                state.dayType = state.nankaiActiveDay; 
                
                if(state.nankaiActiveDay === '平日') { e.target.style.background = '#009688'; e.target.style.color = 'white'; }
                else { e.target.style.background = '#FF9800'; e.target.style.color = 'white'; }
                
                if(deckInstance) renderLayers();
                
                // 💡 2. 補在這裡！當你切換「平日 / 土休日」時，下方的車站時刻表也會瞬間跟著換！
                updateInfoBox(); 
            }
        };
    }

    const selectAllBtn = document.getElementById('btn-select-all'); 
    if (selectAllBtn) {
        selectAllBtn.onclick = () => {
            document.querySelectorAll('.train-type-pill').forEach(pill => {
                const type = pill.getAttribute('data-type');
                state.enabledTypes.add(type);
                pill.style.background = colorPalette[type];
                pill.style.color = '#fff';
            });
            if (deckInstance) renderLayers();
            
            // 💡 3. 補在這裡！點擊「全選」後，讓下方看板立即更新
            updateInfoBox(); 
        };
    }

    const deselectAllBtn = document.getElementById('btn-deselect-all'); 
    if (deselectAllBtn) {
        deselectAllBtn.onclick = () => {
            state.enabledTypes.clear();
            document.querySelectorAll('.train-type-pill').forEach(pill => {
                pill.style.background = 'transparent';
                pill.style.color = 'var(--text-color)';
            });
            state.selectedLine = null; 
            if (deckInstance) renderLayers();
            
            updateInfoBox(); // (你原本這裡就有了，讚！)
        };
    }
}

async function loadData() {
    if (currentRegion === 'TW') {
        const filename = getSelectedDateFilename();
        const yfilename = getYesterdayFilename();
        try {
            const response = await fetch(filename);
            rawData = await response.json();
        } catch (err) { rawData = []; }
        try {
            const yresponse = await fetch(yfilename);
            yrawData = await yresponse.json();
        } catch (err) { yrawData = []; }
    } 
    else if (currentRegion === 'JP') {
        try {
            const res = await fetch(`Japan/Nankai/nankai_timetable.json`);
            rawData = await res.json();
        } catch(e) { rawData = []; }
        yrawData = []; 
    }

    if (state.selectedLine) { 
        state.selectedLine = rawData.find(t => t.number === state.selectedLine.number) || yrawData.find(t => t.number === state.selectedLine.number) || null; 
    }
    
    updateStationGridData();
    updateInfoBox();
    if(deckInstance) renderLayers();
}

function initDeckGL() {
    const todayCalc = new Date();
    state.currentTimeMinutes = todayCalc.getHours() * 60 + todayCalc.getMinutes();
    if (state.currentTimeMinutes < 120) state.currentTimeMinutes += 1440;
    
    deckInstance = new deck.DeckGL({
        container: 'container',
        views: [new deck.OrthographicView({id: 'ortho'})],
        initialViewState: { 
            target: [state.currentTimeMinutes * 3 + 180, state.initialY, 0], 
            zoom: 0, minZoom: -3.75, maxZoom: 20
        },
        controller: true,
        pickingRadius: 10,
        getTooltip: ({object}) => {
            if (object) {
                if (object.number !== undefined) return { text: `${object.train} ${object.number}` };
                else if (object.text === undefined) return { text: `${String(object).split(',')[0]}` };
            }
        },
        onViewStateChange: ({viewState, oldViewState}) => { 
            const MAX_ZOOM = currentRegion === 'JP' ? 15 : 1.5;
            
            // 💡 1. 取得「真正的畫布高度」，避免被瀏覽器工具列干擾導致計算誤差
            const canvasHeight = deckInstance.height || window.innerHeight;
            
            // 💡 2. 加大留白空間：150px 足夠容納車站字體與跨日的突出線條
            const VERTICAL_MARGIN = 150; 
            
            // 💡 3. 精準抓取路線的頭尾座標 (防止有些路線起點不是 0)
            const minD = gridData.minDistance !== undefined ? gridData.minDistance : 0;
            const maxD = gridData.maxDistance !== undefined ? gridData.maxDistance : 0;
            const totalD = maxD - minD;

            // 動態極限縮放計算
            let MIN_ZOOM = -3.75; 
            if (totalD > 0) {
                MIN_ZOOM = Math.log2((canvasHeight - VERTICAL_MARGIN * 2) / totalD);
                MIN_ZOOM = Math.min(MIN_ZOOM, 1.5); 
            }

            // 防溜冰：控制合法 zoom 範圍
            const clampedZoom = Math.min(Math.max(viewState.zoom, MIN_ZOOM), MAX_ZOOM);
            if (viewState.zoom !== clampedZoom) {
                viewState.target = oldViewState.target;
                viewState.zoom = clampedZoom;
            }

            if (currentRegion === 'JP') {
                const scale = Math.pow(2, viewState.zoom);
                const screenHalfHeight = (canvasHeight / 2) / scale;
                const marginUnits = VERTICAL_MARGIN / scale; 
                
                let minY, maxY;
                
                // 判斷是否需要置中
                if (screenHalfHeight * 2 > totalD + marginUnits * 2) {
                    minY = minD + totalD / 2;
                    maxY = minD + totalD / 2;
                } else {
                    // 💡 4. 精準的上下平移極限，加上 minD 確保絕對正確
                    minY = minD + screenHalfHeight - marginUnits; 
                    maxY = maxD - screenHalfHeight + marginUnits; 
                }
                
                viewState.target[1] = Math.min(Math.max(viewState.target[1], minY), maxY);
                viewState.target[0] = Math.min(Math.max(viewState.target[0], 20), 5020);
                
                state.currentZoom = viewState.zoom;
                state.viewState = viewState;
                deckInstance.setProps({viewState});

            } else {
                // ... 🇹🇼 台鐵維持原本的無限循環邏輯不變 ...
                if (viewState.target[1] > state.period) viewState.target[1] -= state.period;
                else if (viewState.target[1] < 0) viewState.target[1] += state.period;
                viewState.target[0] = Math.min(Math.max(viewState.target[0], 20), 5020);
                
                state.currentZoom = viewState.zoom;
                state.viewState = viewState;
                deckInstance.setProps({viewState});
            }
            
            renderLayers();
        },
        onClick: (info) => {
            state.selectedLine = null;
            state.showSchedule = false;
            state.focusedStation = null;
            if (info.object && info.layer.id.includes('main-path-layer')) {
                const trainNumber = info.object.number;
                state.selectedLine = rawData.find(t => t.number === trainNumber) || yrawData.find(t => t.number === trainNumber);
                state.showSchedule = true; 
            } else if (info.object && (info.layer.id.includes('station-layer') || info.layer.id.includes('station-labels'))) {
                state.focusedStation = Array.isArray(info.object) ? info.object[0] : info.object.text;
            }
            updateBottomPanel();
            renderLayers();
            updateInfoBox();
        }
    });
    renderLayers();
}

// ==========================================
// 繪圖與資訊面板更新
// ==========================================
function renderLayers() {
    if (!deckInstance) return;
    // 💡 南海電鐵只需要畫 1 份 (Offset 為 0)，不需要像台鐵畫 3 份
    const yOffsets = currentRegion === 'TW' ? [-state.period, 0, state.period] : [0];
    
    // 處理當日與昨日資料邏輯
    const processTrainData = (sourceData, isYesterday) => {
        return sourceData.filter(train => {
            if (!state.enabledTypes.has(train.train)) return false;
            if (currentRegion === 'JP') {
                const driveStr = train.drive || "";
                const activeStr = state.nankaiActiveDay === '平日' ? '平日' : '土休';
                if (!driveStr.includes(activeStr) && !driveStr.includes("毎日")) return false;
            }
            return state.focusedStation ? train.data.some(p => p.x === state.focusedStation) : true;
        }).flatMap(train => {
            if (currentRegion === 'JP') {
                const seg = [];
                // 💡 只要該車次有停靠目前 state.stationList 裡的任何一站就顯示，不檢查 train.line
                const hasOverlap = train.data.some(p => state.stationList.has(p.x));
                if (!hasOverlap) return [];

                for (let p of train.data) {
                    if (p.y == -1) continue;
                    const cDist = state.stationDistances[p.x];
                    // 💡 只畫出屬於目前路線車站清單內的段落
                    if (cDist !== undefined) {
                        seg.push({ ...p, y: isYesterday ? p.y - 1440 : p.y, adjustedDist: cDist });
                    }
                }
                return seg.length > 1 ? [{ ...train, data: seg }] : [];
            }
            // 臺灣鐵路跨日與山海線偏移計算
            const segments = [];
            let curSeg = [];
            let offset = 0;
            for (let i = 0; i < train.data.length; i++) {
                const p = train.data[i];
                if (p.y == -1) continue;
                
                let py = isYesterday ? p.y - 1440 : p.y;
                if (!isYesterday && py >= 1560) {
                    if (curSeg.length > 0) {
                        const prev = curSeg[curSeg.length - 1];
                        if (prev.y < 1560) {
                            curSeg.push({ ...p, y: 1560, adjustedDist: state.stationDistances[prev.x] + (state.stationDistances[p.x] - state.stationDistances[prev.x]) * (1560 - prev.y) / (p.y - prev.y) + offset});
                        }
                    }
                    continue;
                }
                if (isYesterday && p.y < 1560) continue;

                const cDist = state.stationDistances[p.x];
                if (curSeg.length > 0) {
                    const pDist = state.stationDistances[curSeg[curSeg.length - 1].x];
                    if (pDist < 1000 && cDist > 6000) offset -= state.period;
                    else if (pDist > 6000 && cDist < 1000) offset += state.period;
                }
                if (cDist === undefined) {
                    if (curSeg.length > 1) segments.push({ ...train, data: curSeg });
                    curSeg = [];
                    continue;
                }
                curSeg.push({ ...p, y: py, adjustedDist: cDist + offset });
            }
            if (curSeg.length > 1) segments.push({ ...train, data: curSeg });
            return segments;
        }).filter(t => t.data.length > 1);
    };

    todaySegments = processTrainData(rawData, false);
    yesterdaySegments = processTrainData(yrawData, true);
    const processedSegments = [...todaySegments, ...yesterdaySegments];

    let scheduleData = [];
    if (state.showSchedule && state.selectedLine) {
        const grouped = {};
        const selNum = state.selectedLine.number;
        const isToday = todaySegments.some(t => t.number === selNum);
        const isYest = yesterdaySegments.some(t => t.number === selNum);
        state.selectedLine.data.forEach(p => {
            if (state.stationDistances[p.x] !== undefined && ((isToday && p.y < 1560) || (isYest && p.y >= 1560))) {
                if (!grouped[p.x]) grouped[p.x] = [];
                grouped[p.x].push(isYest ? p.y - 1440 : p.y);
            }
        });
        scheduleData = Object.entries(grouped).map(([name, times]) => {
            times.sort((a, b) => a - b);
            return { station: name, arr: Math.ceil(times[0]), dep: Math.floor(times[1] || times[0]), yCoord: state.stationDistances[name] };
        });
    }

    const activeLabelData = state.currentZoom > 0.8 ? gridData.denseLabelData : state.currentZoom > -0.4 ? gridData.normalLabelData : state.currentZoom > -1.8 ? gridData.sparseLabelData : [];

    const layerBuilder = (offset) => {
        return [
            new deck.PathLayer({
                id: `station-layer-${offset}`, data: Object.entries(state.stationDistances).filter(([n]) => state.stationList.has(n)),
                coordinateSystem: deck.COORDINATE_SYSTEM.CARTESIAN, pickable: true, autoHighlight: true, highlightColor: [220, 220, 220, 150],
                getPath: d => [[270, d[1] + offset], [4770, d[1] + offset]],
                getColor: d => d[0] === state.focusedStation ? (isLight ? [189, 146, 8] : [232, 252, 13]) : (isLight ? [180, 180, 180] : [80, 80, 80]),
                // 💡 鎖定車站橫線為螢幕像素
                widthUnits: 'pixels', getWidth: d => d[0] === state.focusedStation ? 3 : 1
            }),
            new deck.TextLayer({
                id: `station-labels-${offset}`,
                data: state.currentZoom > 0.8 ? gridData.denseLabelData : state.currentZoom > -0.4 ? gridData.normalLabelData : state.currentZoom > -1.8 ? gridData.mainLabelData : [],
                coordinateSystem: deck.COORDINATE_SYSTEM.CARTESIAN, pickable: true, autoHighlight: true, highlightColor: [255, 255, 255, 150],
                getPosition: d => [d.position[0], d.position[1] + offset], getText: d => d.text,
                fontFamily: 'GlowSansSCCom-Compressed, sans-serif',
                // 💡 鎖定文字大小為螢幕像素
                sizeUnits: 'pixels', getSize: 16, 
                getColor: d => d.text === state.focusedStation ? (isLight ? [189, 146, 8] : [232, 252, 13]) : (isLight ? [80, 80, 80] : [180, 180, 180]),
                characterSet: 'auto', getAlignmentBaseline: 'bottom', getTextAnchor: 'middle', pixelOffset: [0, -10]
            }),
            new deck.PathLayer({
                id: `main-path-layer-${offset}`, data: processedSegments, coordinateSystem: deck.COORDINATE_SYSTEM.CARTESIAN,
                pickable: true, autoHighlight: true, highlightColor: [255, 255, 255, 150],
                getPath: d => d.data.map(p => [p.y * 3, p.adjustedDist + offset]),
                getColor: d => { 
                    const h = colorPalette[d.train] || '#999999';
                    return [parseInt(h.substring(1, 3), 16), parseInt(h.substring(3, 5), 16), parseInt(h.substring(5, 7), 16)]; 
                },
                // 💡 鎖定火車斜線永遠是 1 像素寬！
                widthUnits: 'pixels', getWidth: 1
            }),
            new deck.PathLayer({
                id: `selection-layer-${offset}`, data: state.selectedLine && state.enabledTypes.has(state.selectedLine.train) ? processedSegments.filter(s => s.number === state.selectedLine.number) : [],
                coordinateSystem: deck.COORDINATE_SYSTEM.CARTESIAN, pickable: false,
                getPath: d => d.data.map(p => [p.y * 3, p.adjustedDist + offset]),
                getColor: isLight ? [255, 214, 0] : [255, 196, 0], 
                // 💡 鎖定高亮線為 4 像素寬
                widthUnits: 'pixels', getWidth: 3
            }),
            new deck.TextLayer({
                id: `train-schedule-labels-${offset}`, data: scheduleData, coordinateSystem: deck.COORDINATE_SYSTEM.CARTESIAN,
                getPosition: d => [(d.dep+1.5) * 3, d.yCoord + offset, 0],
                getText: d => { const f = v => `${Math.floor(v/60).toString().padStart(2,'0')}${(v%60).toString().padStart(2,'0')}`; return `${f(d.arr)} - ${f(d.dep)} ${d.station}`; },
                fontFamily: 'GlowSansSCCom-Compressed, sans-serif',
                getSize: 11, sizeMaxPixels: 11, sizeMinPixels: 0, getColor: isLight ? [50, 50, 50] : [220, 220, 220],
                characterSet: 'auto',
                getTextAnchor: 'start', getAlignmentBaseline: 'center', pixelOffset: [15, 0], background: true, getBackgroundColor: isLight ? [255, 255, 255, 180] : [0, 0, 0, 180]
            }),
            new deck.TextLayer({
                id: `station-labels-highlight-${offset}`, data: activeLabelData.filter(d => d.text === state.focusedStation),
                coordinateSystem: deck.COORDINATE_SYSTEM.CARTESIAN, pickable: true,
                getPosition: d => [d.position[0], d.position[1] + offset], getText: d => d.text,
                fontFamily: 'GlowSansSCCom-Compressed, sans-serif',
                getSize: 16, sizeMaxPixels: 16, sizeMinPixels: 0, getColor: isLight ? [189, 146, 8] : [232, 252, 13],
                characterSet: 'auto',
                getAlignmentBaseline: 'bottom', getTextAnchor: 'middle', pixelOffset: [0, -10], background: true, getBackgroundColor: isLight ? [235, 235, 235, 180] : [20, 20, 20, 180]
            })
        ];
    };

    const timeLinePadding = currentRegion === 'JP' ? 0 : state.period;
    deckInstance.setProps({ layers: [
        new deck.PathLayer({ id: 'thin-time-lines', data: gridData.thinLines, getPath: d => d.path, getColor: isLight ? [200, 200, 200] : [50, 50, 50], getWidth: 1, widthMaxPixels: 2, widthMinPixels: 0 }),
        new deck.PathLayer({ id: 'thick-time-lines', data: gridData.thickLines, getPath: d => d.path, getColor: isLight ? [180, 180, 180] : [80, 80, 80], getWidth: 2, widthMaxPixels: 3, widthMinPixels: 0 }),
        new deck.TextLayer({ id: 'vertical-labels', 
            data: state.currentZoom > 0.8 ? gridData.denseLabels : state.currentZoom > -0.4 ? gridData.normalLabels : state.currentZoom > -1.6 ? gridData.sparseLabels : state.currentZoom > -2 ? gridData.simpleLabels : [],
            getPosition: d => d.position, getText: d => d.text, 
            fontFamily: 'GlowSansSCCom-Compressed, sans-serif', // 💡 改成明確的字體名稱
            getSize: 12, sizeMaxPixels: 12, sizeMinPixels: 0, getColor: isLight ? [80, 80, 80] : [180, 180, 180], characterSet: 'auto', getAlignmentBaseline: 'top', getTextAnchor: 'start', pixelOffset: [5, 5]
        }),
        new deck.ScatterplotLayer({ id: 'json-layer', data: rawData.flatMap(g => g.data.map(p => ({...p, train: g.train}))), getPosition: d => [d.y*3, state.stationDistances[d.x]], getFillColor: isLight? [50, 50, 50] : [200, 200, 200], getRadius: 0.0001, radiusMaxPixels: 0.001, radiusMinPixels: 0.00001 }),
        ...yOffsets.flatMap(layerBuilder),
        new deck.PathLayer({ 
            id: 'current-time-line', 
            // 💡 修正：把 state.period 換成 timeLinePadding
            data: [{ path: [[state.currentTimeMinutes * 3, gridData.minDistance - timeLinePadding], [state.currentTimeMinutes * 3, gridData.maxDistance + timeLinePadding]] }], 
            getPath: d => d.path, 
            getColor: isLight ? [0, 172, 193] : [0, 225, 255], 
            
            // 💡 鎖定像素，讓時間線不會放大後變太粗
            widthUnits: 'pixels', 
            getWidth: 3
        })
    ]});
}

function updateInfoBox() {
    if(DOM.btnClearSelection) DOM.btnClearSelection.style.display = 'block';
    const formatTime = (totalMin) => `${String(Math.floor((totalMin % 1440) / 60)).padStart(2, '0')}:${String(Math.floor(totalMin % 60)).padStart(2, '0')}`;
    
    if (state.selectedLine) {
        // 💡 防彈機制 1：建立安全物件，台日資料結構都能無縫接軌！
        const infoObj = state.selectedLine.info || {}; 
        
        const daysLabel = ["加", "一", "二", "三", "四", "五", "六", "日", "例"];
        
        // 💡 防彈讀取 via (山海線)
        const viaRaw = infoObj.via;
        const viaText = (viaRaw && viaRaw !== '-') ? `(${viaRaw.replace(/線/g, '')})` : '';
        const viaColor = viaText.includes("山") ? "#4CAF50" : viaText.includes("海") ? "#2196F3" : viaText.includes("成追") ? "#FF5722" : "#888";
        
        // 💡 防彈讀取附註 (note)
        const specialNote = (infoObj.note || state.selectedLine.note || "").split('。')[0];
        
        let boxesHtml = `<div class="day-container" title="${specialNote}">`;
        [0,1,2,3,4,5,6,7,8].forEach(num => {
            // 💡 防彈讀取行駛日 (drive)
            const driveStr = infoObj.drive || state.selectedLine.drive || "平日土休";
            const isActive = driveStr.includes(num.toString()) || driveStr.includes("平日") || driveStr.includes("土休") || driveStr.includes("毎日");
            boxesHtml += `<div class="day-box ${isActive ? 'active' : ''} ${(num===8 && driveStr.includes("9")) ? 'special-rule' : ''}">${daysLabel[num]}</div>`;
        });
        boxesHtml += '</div><div class="service-container">';
        
        Object.entries(serviceIcons).forEach(([name, url]) => {
            const imgStr = infoObj.img || state.selectedLine.img || "";
            const noteStr = infoObj.note || state.selectedLine.note || "";
            if (imgStr.includes(name) || noteStr.includes(name)) {
                boxesHtml += `<div class="service-box" title="${name}"><img src="${url}" alt="${name}"></div>`;
            }
        });
        boxesHtml += '</div>';

        // 💡 1. 跨線直通拼圖：直接去「原始大資料庫 (rawData)」找，無視當前顯示哪條線
        const targetNum = String(state.selectedLine.number).trim();
        const baseTime = state.selectedLine.data[0].y; 

        // 這裡直接對全域的 rawData 和 yrawData 進行過濾
        const allTrainFragments = [...rawData, ...yrawData].filter(t => {
            const isSameNumber = String(t.number).trim() === targetNum;
            // 增加容錯：除了號碼一樣，第一站的時間也要在合理範圍內 (例如 10 小時內)
            const isSameRun = Math.abs(t.data[0].y - baseTime) < 600; 
            return isSameNumber && isSameRun;
        });
        
        let mergedTrainData = [];
        allTrainFragments.forEach(fragment => {
            mergedTrainData = mergedTrainData.concat(fragment.data);
        });
        
        // 依照時間排序，確保「難波 -> 泉佐野」接上「泉佐野 -> 關西空港」
        mergedTrainData.sort((a, b) => a.y - b.y);

        // 💡 2. 改用「完整拼圖資料 (mergedTrainData)」來計算沿途停靠站
        const stopsMap = mergedTrainData.reduce((acc, curr) => {
            if (!acc[curr.x]) acc[curr.x] = { arr: null, dep: null };
            if (acc[curr.x].arr === null) acc[curr.x].arr = Math.ceil(curr.y);
            else acc[curr.x].dep = Math.floor(curr.y);
            return acc;
        }, {});

        // 💡 完美對齊版：將站名、時間、箭頭劃分出精準的「網格區塊」
        const stationsHtml = Object.entries(stopsMap).map(([name, times], index, arr) => {
            const arrStr = times.arr !== null ? formatTime(times.arr) : "--:--";
            const depStr = times.dep !== null ? formatTime(times.dep) : (times.arr !== null ? formatTime(times.arr) : "--:--");
            const focusedClass = name === state.focusedStation ? 'focused' : '';
            const isLast = index === arr.length - 1; // 判斷是不是最後一站
            
            return `
                <div class="timeline-block">
                    <div class="station-col ${focusedClass}" onclick="selectStation('${name}')">
                        <div class="stop-name">${name}</div>
                        <div class="stop-time">${arrStr}</div>
                        <div class="stop-time sub-time">${depStr}</div>
                    </div>
                    ${isLast ? '' : `
                    <div class="arrow-col">
                        <div class="arrow-spacer"></div>
                        <div class="track-arrow">➔</div>
                    </div>
                    `}
                </div>
            `;
        }).join(''); // 💡 箭頭已經在上面處理了，所以這裡清空 
        
        // 💡 3. 直接從「完整軌跡」抓取最真實的起終點！
        // (不需要再寫 if 去攔截泉佐野了，因為系統現在知道它真的開到了關西空港)
        const trueStartStation = mergedTrainData[0].x;
        const trueEndStation = mergedTrainData[mergedTrainData.length - 1].x;
        const trainColor = colorPalette[state.selectedLine.train] || '#ccc';

        DOM.infoBox.innerHTML = `
            <div class="train-detail-layout">
                <div class="sticky-train-header" style="color: ${trainColor};">
                    <strong>${state.selectedLine.train} ${state.selectedLine.number}</strong>
                </div>
                
                <div class="metadata-group">
                    <span class="info-segment via-label" style="color: ${viaColor}">${viaText}</span>
                    <span class="info-segment route-display">${trueStartStation} → ${trueEndStation}</span>
                    ${boxesHtml}
                </div>
                
                <div class="stations-track">
                    ${stationsHtml}
                </div>
            </div>
        `;
    } else if (state.focusedStation) {
        const nextTrains = [...todaySegments, ...yesterdaySegments]
            // 1. 基本過濾 (車種、平日/假日)
            .filter(train => {
                if (state.enabledTypes && !state.enabledTypes.has(train.train)) return false;
                const driveStr = train.info?.drive || train.drive || "";
                if (state.dayType === '平日' && driveStr.includes('土休') && !driveStr.includes('平日')) return false;
                if (state.dayType === '土休日' && driveStr.includes('平日') && !driveStr.includes('土休')) return false;
                return true;
            })
            // 2. 轉換資料，並在這裡啟動「全域直通縫合」尋找真終點！
            .map(train => {
                const stop = train.data.findLast(p => p.x === state.focusedStation);
                if (!stop) return null; // 防呆：這班車如果沒停這站就跳過
                
                const stopDistances = train.data.map(p => allStationDistances[p.x] || state.stationDistances[p.x]).filter(d => d !== undefined);
                const infoSafe = train.info || {};
                
                const isClockwise = currentRegion === 'TW' 
                    ? (allStationDistances[infoSafe.start?.slice(6)] > allStationDistances[infoSafe.end?.slice(6)]) ^ (Math.max(...stopDistances) - Math.min(...stopDistances) > 6000) 
                    : state.stationDistances[train.data[0].x] < state.stationDistances[train.data[train.data.length-1].x];
                
                let destName = "";
                if (currentRegion === 'TW') {
                    destName = (infoSafe.end || "").slice(6);
                } else {
                    // 💡 跨線直通終極解法：去全域資料庫找這班車真正的終點！
                    const targetNum = String(train.number).trim();
                    const baseTime = train.data[0].y;
                    
                    const allFragments = [...rawData, ...yrawData].filter(t => 
                        String(t.number).trim() === targetNum && 
                        Math.abs(t.data[0].y - baseTime) < 600
                    );
                    
                    let mergedData = [];
                    allFragments.forEach(f => { mergedData = mergedData.concat(f.data); });
                    mergedData.sort((a, b) => a.y - b.y);
                    
                    // 取得縫合後的真正最後一站 (不用寫死泉佐野了！)
                    if (mergedData.length > 0) {
                        destName = mergedData[mergedData.length - 1].x;
                    } else {
                        destName = train.data[train.data.length-1].x;
                    }
                    destName = destName.replace(/.* /, ''); // 清除可能帶有的前綴
                }
                
                return { number: train.number, type: train.train, dest: destName, time: stop.y, isClockwise };
            })
            .filter(t => t !== null && t.time >= state.currentTimeMinutes)
            .sort((a, b) => a.time - b.time);
        
        // 💡 終極物理去重法：直接忽略車次號碼 (解決幽靈雙胞胎)
        // 只要這班車在「同一個時間」發車、「車種」一樣、且「目的地」一樣，在物理上絕對是同一班車，殺掉分身！
        const uniqueNextTrains = nextTrains.filter((train, index, self) =>
            index === self.findIndex((t) => 
                t.time === train.time && 
                t.type === train.type && 
                t.dest === train.dest 
            )
        );

        // --- 以下是生成 HTML 畫面的部分 ---
        const createTrainBadge = (t) => {
            const trainColor = colorPalette[t.type] || '#ccc';
            const opacity = t.dest === state.focusedStation ? 0.5 : 1;
            return `<span class="train-item-badge" onclick="selectTrain('${t.number}')">
                        <span style="color: ${trainColor}; opacity: ${opacity}; margin-right: 5px;">${t.type} ${t.number}</span>
                        <span style="opacity: ${opacity};">${formatTime(t.time)} 往 ${t.dest}</span>
                    </span>`;
        };

        const buildInfoList = (list) => {
            if (!list.length) return `<span class="direction-label">無後續車次</span>`;
            return list.map(createTrainBadge).join('<b class="separator-arrow">>></b>');
        };
        
        // ✅ 確保我們丟給畫面的是過濾後的 uniqueNextTrains
        const cwtext = buildInfoList(uniqueNextTrains.filter(t => t.isClockwise));
        const ccwtext = buildInfoList(uniqueNextTrains.filter(t => !t.isClockwise));

        DOM.stationBox.innerHTML = `
            <div class="station-info-container">
                <div class="station-name-header">
                    <strong>${state.focusedStation}站</strong>
                </div>
                <div class="train-list-container">
                    <div class="train-direction-row">
                        <span class="direction-label">順行</span>
                        <b class="separator-arrow">>></b>
                        ${cwtext}
                    </div>
                    <div class="train-direction-row">
                        <span class="direction-label">逆行</span>
                        <b class="separator-arrow">>></b>
                        ${ccwtext}
                    </div>
                </div>
            </div>
        `;
    } else {
        if(DOM.stationBox) DOM.stationBox.innerHTML = '';
        if(DOM.infoBox) DOM.infoBox.innerHTML = '';
    }
}

function updateStationGridData() {
    Object.keys(gridData).forEach(key => Array.isArray(gridData[key]) ? gridData[key] = [] : null);
    Object.entries(state.stationDistances).forEach(([name, yValue]) => {
        if (state.stationList.has(name)) {
            for (let x = 120; x <= 1560; x += 120) {
                const entry = { text: name, position: [x * 3, yValue], y: yValue };
                if (x % 480 === 0) {
                    // 💡 修正 1：讓南海電鐵的所有車站都能強制成為「主要顯示標籤」
                    if (mainStationList.has(name) || currentRegion === 'JP') gridData.mainLabelData.push(entry);
                    gridData.sparseLabelData.push(entry);
                }
                if (x % 240 === 0) gridData.normalLabelData.push(entry);
                gridData.denseLabelData.push(entry);
            }
        }
    });

    const distances = Array.from(state.stationList).map(name => state.stationDistances[name]);
    gridData.minDistance = Math.min(...distances);
    gridData.maxDistance = Math.max(...distances);

    // 💡 加上 Padding 讓畫面邊緣不要太擠
    const yPadding = currentRegion === 'JP' ? 0 : state.period;
    const minY = gridData.minDistance - yPadding;
    const maxY = gridData.maxDistance + yPadding;
    
    for (let x = 120; x <= 1560; x += 10) {
        const path = [[x * 3, minY], [x * 3, maxY]];
        (x % 60 === 0) ? gridData.thickLines.push({ path }) : gridData.thinLines.push({ path });
    }

    // 💡 修正 2：針對南海電鐵較短的 Y 軸距離，動態縮小時間標籤的繪製間隔
    const yStep1 = currentRegion === 'JP' ? 100 : 400;
    const yStep2 = currentRegion === 'JP' ? 200 : 800;

    for (let y = minY; y <= maxY; y += yStep1) {
        for (let x = 120; x <= 1560; x += 10) {
            const label = { text: `${Math.floor(x/60).toString().padStart(2, '0')}${(x%60).toString().padStart(2, '0')}`, position: [(x*3)+5, y] };
            gridData.denseLabels.push(label);
            if (x % 30 === 0) gridData.normalLabels.push(label);
        }
    }
    for (let y = minY; y <= maxY; y += yStep2) {
        for (let x = 120; x <= 1560; x += 60) {
            const label = { text: `${Math.floor(x/60).toString().padStart(2, '0')}${(x%60).toString().padStart(2, '0')}`, position: [(x*3)+5, y] };
            gridData.sparseLabels.push(label);
            if (x % 120 === 0) gridData.simpleLabels.push(label);
        }
    }
}

function updateBottomPanel() {
    ['view-train', 'view-station', 'view-null'].forEach(id => { const el = document.getElementById(id); if(el) el.classList.add('hidden'); });
    if (state.selectedLine && document.getElementById('view-train')) document.getElementById('view-train').classList.remove('hidden');
    else if (state.focusedStation && document.getElementById('view-station')) document.getElementById('view-station').classList.remove('hidden');
    else if (document.getElementById('view-null')) document.getElementById('view-null').classList.remove('hidden');
}

// ==========================================
// 全域事件與控制綁定
// ==========================================
if (document.getElementById('bottompanel')) document.getElementById('bottompanel').addEventListener('wheel', (e) => { if (e.deltaY !== 0) { e.preventDefault(); e.currentTarget.scrollLeft += e.deltaY * 3; } }, { passive: false });

const sidebar = document.getElementById('sidebar');
const toggleBtn = document.getElementById('sidebar-toggle');
if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
        const isCollapsed = sidebar.classList.toggle('collapsed');
        toggleBtn.style.right = isCollapsed ? '0px' : '25vw'; 
        const icon = toggleBtn.querySelector('.icon');
        if(icon) icon.textContent = isCollapsed ? '❮' : '❯'; 
        document.getElementById('main-wrapper').classList.toggle('sidebar-collapsed');
    });
}

const themeToggle = document.getElementById('theme-toggle');
if (themeToggle) {
    themeToggle.addEventListener('click', () => {
        document.body.classList.toggle('light-theme');
        isLight = document.body.classList.contains('light-theme');
        document.getElementById('theme-icon').textContent = isLight ? '🌙' : '☀️';
        localStorage.setItem('theme', isLight ? 'light' : 'dark');
        colorPalette = currentRegion === 'TW' ? (isLight ? lightcolorPalette : darkcolorPalette) : jpColorPalette;
        updateStationGridData(); renderLayers(); updateInfoBox();
    });
}
if (localStorage.getItem('theme') === 'light') { document.body.classList.add('light-theme'); isLight = true; if(document.getElementById('theme-icon')) document.getElementById('theme-icon').textContent = '🌙'; }
if (dateSelector) dateSelector.addEventListener('change', loadData);

if (DOM.btnSelectAll) DOM.btnSelectAll.addEventListener('click', () => { Object.keys(colorPalette).forEach(t => state.enabledTypes.add(t)); document.querySelectorAll('.train-type-pill').forEach(p => { p.style.background = colorPalette[p.getAttribute('data-type')]; p.style.color = '#fff'; p.classList.add('active'); }); if(deckInstance) renderLayers(); updateInfoBox(); });
if (DOM.btnDeselectAll) DOM.btnDeselectAll.addEventListener('click', () => { state.enabledTypes.clear(); state.selectedLine = null; document.querySelectorAll('.train-type-pill').forEach(p => { p.style.background = 'transparent'; p.style.color = 'var(--text-color)'; p.classList.remove('active'); }); if(deckInstance) renderLayers(); updateInfoBox(); });
if (DOM.btnClearSelection) DOM.btnClearSelection.onclick = () => { state.selectedLine = null; state.showSchedule = false; updateInfoBox(); updateBottomPanel(); if(deckInstance) renderLayers(); };

document.addEventListener('keydown', (e) => {
    const key = e.key.toLowerCase();
    if (key === 'h' && state.selectedLine) { state.showSchedule = !state.showSchedule; if(deckInstance) renderLayers(); }
    if (key === 'm' && DOM.viewMonitor) DOM.viewMonitor.style.display = DOM.viewMonitor.style.display === 'block' ? 'none' : 'block';
    if (key === 'r') { realtime = !realtime; loadData(); }
    if (key === "escape" || e.keyCode === 27) { state.focusedStation = null; state.selectedLine = null; state.showSchedule = false; ['info-modal', 'question-modal'].forEach(id => { const m = document.getElementById(id); if(m) m.style.display = 'none'; }); updateInfoBox(); updateBottomPanel(); if(deckInstance) renderLayers(); }
});

// Modal Logic
['info', 'question'].forEach(id => {
    const btn = document.getElementById(`btn-${id}`), modal = document.getElementById(`${id}-modal`), closeBtn = document.querySelector(`.close-${id}modal`);
    if(btn) btn.addEventListener('click', () => modal.style.display = 'flex');
    if(closeBtn) closeBtn.addEventListener('click', () => modal.style.display = 'none');
    window.addEventListener('click', e => { if (e.target === modal) modal.style.display = 'none'; });
});

window.selectTrain = function(trainNumber) {
    const selected = [...rawData, ...yrawData].find( t => t.number == trainNumber );
    if (selected) { state.selectedLine = selected; state.showSchedule = true; state.focusedStation = null; updateBottomPanel(); renderLayers(); updateInfoBox(); }
};

// 💡 攝影機導航：無動畫、瞬間切換，並自動縮放至「完美填滿螢幕」的比例！(Auto-Fit 版)
window.centerCameraOnLine = function() {
    if (!deckInstance || !state.stationList || !state.stationDistances) return;

    const distances = Array.from(state.stationList)
                           .map(name => state.stationDistances[name])
                           .filter(d => d !== undefined);
    
    if (distances.length === 0) return;

    const currentVS = state.viewState || deckInstance.props.viewState || deckInstance.props.initialViewState || {};
    const currentX = currentVS.target?.[0] || (state.currentTimeMinutes * 3 + 180);

    const minD = gridData.minDistance !== undefined ? gridData.minDistance : Math.min(...distances);
    const maxD = gridData.maxDistance !== undefined ? gridData.maxDistance : Math.max(...distances);
    const totalD = maxD - minD;

    const canvasHeight = deckInstance.height || window.innerHeight;
    const VERTICAL_MARGIN = 150; 

    // --- 💡 核心修復 1：智慧計算「完美滿版」的 Zoom ---
    let idealZoom = -3.75;
    if (totalD > 0) {
        // 算出剛好能把整條路線塞進螢幕高度的比例
        idealZoom = Math.log2((canvasHeight - VERTICAL_MARGIN * 2) / totalD);
        // 限制極限，避免超短路線(如只有兩站)被放得過大
        idealZoom = Math.min(idealZoom, 1.5); 
    }
    
    // 💡 直接採用這個完美的比例！
    const currentZoom = idealZoom;

    // --- 💡 核心修復 2：用完美的 Zoom 來算置中座標 ---
    const scale = Math.pow(2, currentZoom);
    const screenHalfHeight = (canvasHeight / 2) / scale;
    const marginUnits = VERTICAL_MARGIN / scale;

    let targetY;
    // 因為我們已經調成了滿版比例，整條線剛好裝得下，直接給它「置中對齊」最漂亮！
    if (screenHalfHeight * 2 >= totalD + marginUnits * 2 - 1) { 
        targetY = minD + totalD / 2;
    } else {
        targetY = minD + screenHalfHeight - marginUnits; 
    }

    const updatedViewState = { 
        ...currentVS, 
        target: [currentX, targetY, 0],
        zoom: currentZoom // 💡 帶著完美的縮放比例飛過去
    };
    
    state.viewState = updatedViewState; 
    state.currentZoom = currentZoom; // 💡 同步更新，確保圖層知道現在的比例

    deckInstance.setProps({ viewState: updatedViewState });
    
    // 💡 強制重繪！確保車站的標籤 (Label) 密度與新的 Zoom 瞬間同步！
    renderLayers(); 
};

window.selectStation = function(stationName) {
    if (!stationName) return;
    if (state.stationDistances[stationName] === undefined) {
        if (mountStationDistances[stationName] !== undefined) [...document.querySelectorAll('.line-pill')].find(p => p.getAttribute('data-line') === 'mountain')?.click();
        else if (seaStationDistances[stationName] !== undefined) [...document.querySelectorAll('.line-pill')].find(p => p.getAttribute('data-line') === 'sea')?.click();
    }
    if (state.stationDistances[stationName] !== undefined) {
        state.selectedLine = null; state.showSchedule = false; state.focusedStation = stationName; 
        const currentVS = deckInstance.props.viewState || state.viewState || {};
        const updatedViewState = { ...currentVS, target: [currentVS.target?.[0] || state.currentTimeMinutes * 3 + 180, state.stationDistances[stationName], 0], transitionDuration: 400, transitionInterpolator: new deck.LinearInterpolator(['target']), transitionInterruption: 1 };
        state.viewState = updatedViewState; deckInstance.setProps({ viewState: updatedViewState });
        updateBottomPanel(); renderLayers(); updateInfoBox(); 
    }
};