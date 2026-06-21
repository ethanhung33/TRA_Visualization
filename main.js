// ==========================================
// 1. DOM 元素綁定與全域變數
// ==========================================
const canvas = document.getElementById('diaCanvas');
const ctx = canvas.getContext('2d');

// UI 控制項
let currentRouteView = ""; // 🌟 改成空字串，動態指派
const trainTypeContainer = document.getElementById('train-type-container');
const btnAllTrains = document.getElementById('btn-all-trains');
const btnNoTrains = document.getElementById('btn-no-trains');

// 🌟 就是漏了這一行！用來抓取 HTML 裡的太陽按鈕
const btnTheme = document.getElementById('btn-theme');

const CONFIG = {
    paddingLeft: 120,   // 🌟 從 100~200 縮減到 60 (剛好夠 0:00 線跟標籤的空間)
    paddingTop: 50,
    scaleX: 1.0,
    scaleY: 1.0
};
const SIDE_MARGIN = 150; // 🌟 這是你想要的「左右留白」寬度，數值越大留白越多
const TOTAL_MINUTES = 1560; // 26 小時

let renderFrame = null;

// 資料狀態
let topology = null;
let timetable = [];
let lookupY = {}; 
let loopKm = 0;      // 台灣環島一圈的總公里數
let loopHeight = 0;  // 環島一圈在畫布上的像素高度
let globalStationMap = {};
let junctionCache = {};

let camera = { x: 0, y: 0 };

let stationCoords = [];

let selectedTrain = null;
let hoveredTrain = null;
let selectedStation = null; // 加在 let selectedTrain = null; 旁邊
let hoveredStation = null;

let cachedPartnerIds = new Set();
let cachedStationChainSet = null;

let availableDates = [];
let currentDate = "";

// 🌟 還有這兩個主題狀態的變數也要確保有宣告到
let settings = null;        
let isDarkMode = true;      

// ... (往下繼續是你原本的程式碼) ...
// 視角與過濾狀態 
let activeTrainTypes = new Set(); 

let currentSystemPath = "";

let renderIntervalId = null;

let isThemeBound = false; // 🌟 新增：用來記錄主題按鈕是不是已經綁定過了

let isInteractionsBound = false; // 🌟 新增：紀錄互動事件是否已綁定

let isHomeBound = false; // 全域變數

// ==========================================
// 🌟 台日異體字與漢字轉換字典
// ==========================================
const KANJI_MAP = {
    '臺': '台',   // 台臺互通
    '関': '關',   // 関西、関東
    '静': '靜',   // 静岡
    '広': '廣',   // 広島
    '沢': '澤',   // 軽井沢、金沢
    '浜': '濱',   // 浜松、横浜
    '鉄': '鐵',   // 電鉄
    '豊': '豐',   // 豊橋
    '姫': '姬',   // 姫路
    '桜': '櫻',   // 桜島
    '渋': '澀',   // 渋谷
    '条': '條',   // 九条
    '乗': '乘',   // 乗車
    '気': '氣',   // 電気
    '区': '區',   // 都区内
    '国': '國',   // 国鉄
    '嶋': '島',   // 異體字
    '徳': '德',   // 德山
    '戸': '戶',   // 神戸
    '満': '滿',   // 天満
    '応': '應',   // 天応
    '莱': '萊',   // 蓬萊
};

/**
 * 將字串進行正規化，把日文漢字或異體字統一轉為標準繁體字，並轉為小寫
 */
function normalizeText(text) {
    if (!text) return "";
    let result = text;
    // 遍歷字典，將所有字串內的異體字無差別替換為標準字
    for (let jp in KANJI_MAP) {
        let tw = KANJI_MAP[jp];
        result = result.split(jp).join(tw);
    }
    return result.toLowerCase();
}

// 🌟 事件代理：這輩子只綁定一次，且無論 UI 怎麼重刷都有效
document.addEventListener('click', (e) => {
    // 透過 ID 判斷點擊的是哪一個系統按鈕 (請確認你首頁按鈕的 ID 是這兩個)
    if (e.target.id === 'btn-tra') {
        init('data/Taiwan/TRA/');
    } else if (e.target.id === 'btn-hsr') {
        init('data/Taiwan/HSR/');
    }
});

// ==========================================
// 🌍 系統專屬時區轉換器 (Timezone Adapter)
// ==========================================
function getCurrentSystemMinutes() {
    const now = new Date();

    // 防呆：如果 json 沒寫時區，就乖乖用使用者的本地裝置時間
    if (!settings || settings.timezone_offset === undefined) {
        return now.getHours() * 60 + now.getMinutes();
    }

    // 1. 抓出絕對標準的 UTC 世界協調時間 (總分鐘數)
    let utcMinutesTotal = now.getUTCHours() * 60 + now.getUTCMinutes();

    // 2. 加上該系統專屬的時區偏移量 (例如日本是 +9，9 * 60 = 540 分鐘)
    let systemMinutes = utcMinutesTotal + (settings.timezone_offset * 60);

    // 3. 處理跨日問題，保證數值完美落在 0 ~ 1439 的區間內循環
    return ((systemMinutes % 1440) + 1440) % 1440;
}

// ==========================================
// 🌟 全域變數：純停靠次數權重 (防交會站重複計算版)
// ==========================================
window.globalStationWeights = {};

function calculateStationWeights() {
    window.globalStationWeights = {};
    if (!timetable) return;

    timetable.forEach(train => {
        if (!train.segments) return;

        // 🌟 準備一個袋子 (Set)，用來記錄這班車「已經給過分數」的車站
        let countedStations = new Set();

        train.segments.forEach(seg => {
            for (let i = 0; i < seg.s.length; i++) {
                // v !== 2 代表這站有停靠
                if (seg.v[i] !== 2) {
                    let stId = String(seg.s[i]);
                    
                    // 🌟 核心防護：如果這班車「還沒」幫這個站加過分，才加分！
                    if (!countedStations.has(stId)) {
                        // 單純計數：每停一班車就 +1 分
                        window.globalStationWeights[stId] = (window.globalStationWeights[stId] || 0) + 1;
                        
                        // 登記：這班車已經給過這個站分數了，下次同班車再看到它(跨線交會)就不給了！
                        countedStations.add(stId); 
                    }
                }
            }
        });
    });
}


// ==========================================
// 2. 核心換算函式
// ==========================================
function timeToX(minutes) {
    return CONFIG.paddingLeft + (minutes * CONFIG.scaleX);
}

function getCircularCopyRange(loopH, vTop, vBottom) {
    if (!(loopH > 0)) return { copyStart: -1, copyEnd: 1 };
    const cStart = Math.floor((vTop - CONFIG.paddingTop - loopH) / loopH);
    const cEnd   = Math.ceil((vBottom - CONFIG.paddingTop - loopH) / loopH);
    return { copyStart: cStart - 1, copyEnd: cEnd + 1 };
}

// ==========================================
// 🌟 智慧路線整理器：自動判斷交會站並翻轉方向
// ==========================================
function getProcessedSegments(selectedSegments, topology) {
    // 1. 先把所有路線的車站名單抓出來
    let segmentsData = selectedSegments.map(segInput => {
        let segId = typeof segInput === 'string' ? segInput : segInput.id;
        let seg = topology.segments.find(s => s.id === segId);
        if (!seg) return null;
        
        let stations = [...seg.stations];
        let userReversed = false;
        
        // 處理區間截取
        if (typeof segInput === 'object') {
            let sIdx = 0, eIdx = seg.stations.length - 1;
            if (segInput.start) sIdx = seg.stations.findIndex(st => st.name === segInput.start || st.id === segInput.start);
            if (segInput.end) eIdx = seg.stations.findIndex(st => st.name === segInput.end || st.id === segInput.end);
            
            if (sIdx !== -1 && eIdx !== -1) {
                stations = seg.stations.slice(Math.min(sIdx, eIdx), Math.max(sIdx, eIdx) + 1);
                if (sIdx > eIdx) { stations.reverse(); userReversed = true; }
            }
        }
        return { segId, stations, userReversed };
    }).filter(Boolean);


    let isCircular = false;
    if (settings && settings.view_presets) {
        for (let key in settings.view_presets) {
            if (settings.view_presets[key].lines === selectedSegments) {
                if (settings.view_presets[key].view_type === "CIRCULAR") {
                    isCircular = true;
                }
                break;
            }
        }
    }

    if (isCircular) {
        // 如果這個環狀線剛好是由「2 條路線」組成
        if (segmentsData.length === 2) {
            let seg1 = segmentsData[0].stations;
            let seg2 = segmentsData[1].stations;
            
            let tailOfFirst = seg1[seg1.length - 1].id;
            let headOfSecond = seg2[0].id;
            
            // 比較第一段的尾巴跟第二段的頭
            if (tailOfFirst !== headOfSecond) {
                // 不一樣！啟動自我修復：把第二段反轉
                segmentsData[1].stations.reverse();
            }
        }
        // 處理完畢，直接回傳，跳過下方容易錯亂的直線翻轉演算法
        return segmentsData; 
    }

    // 2. 自動判斷是否需要翻轉
    for (let i = 0; i < segmentsData.length; i++) {
        if (segmentsData[i].userReversed) continue; // 使用者已手動翻轉，不干涉

        if (i < segmentsData.length - 1) {
            // 如果有下一條線，看交會站在哪
            let curr = segmentsData[i].stations;
            let next = segmentsData[i+1].stations;
            let commonIdx = curr.findIndex(st => next.some(nst => nst.id === st.id));
            
            // 如果交會站在前半段，代表這條線背對著下一條線，轉頭！
            if (commonIdx !== -1 && commonIdx < curr.length / 2) curr.reverse();
            
        } else if (i > 0) {
            // 如果是最後一條線，看上一條線的最後一站
            let curr = segmentsData[i].stations;
            let prevLast = segmentsData[i-1].stations[segmentsData[i-1].stations.length - 1];
            let commonIdx = curr.findIndex(st => st.id === prevLast.id);
            
            // 如果交會站在後半段，必須轉頭把交會站接到前面！
            if (commonIdx !== -1 && commonIdx >= curr.length / 2) curr.reverse();
        }
    }
    return segmentsData;
}


// ==========================================
// 繪製背景網格 (攤平展開版)
// ==========================================
function drawGrid(viewKey, layer = 'all') {
    lookupY = {}; 
    let currentAccumulatedKm = 0; 

    // 🌟 新增：找出目前的最高權重，當作比例尺基準
    let maxWeight = 1; 
    if (topology && topology.segments) {
        topology.segments.forEach(seg => {
            seg.stations.forEach(st => {
                if (st.weight > maxWeight) maxWeight = st.weight;
            });
        });
    }

    let presetKey = viewKey; 
    let selectedSegments = settings?.view_presets?.[presetKey]?.lines || [];
    let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";

    if (selectedSegments.length === 0) return; 

    // 1. 整理唯一車站
    let uniqueStations = [];
    let segmentsData = getProcessedSegments(selectedSegments, topology);

    segmentsData.forEach(data => {
        let stationsToDraw = data.stations;
        let segId = data.segId;

        let segMaxKm = 0;
        let startKm = stationsToDraw[0].km; 

        stationsToDraw.forEach(st => {
            let relativeKm = Math.abs(st.km - startKm); 
            let absoluteKm = currentAccumulatedKm + relativeKm;
            let yPos = absoluteKm * CONFIG.scaleY;

            if (!lookupY[st.id]) lookupY[st.id] = [];
            
            let lastOpt = lookupY[st.id][lookupY[st.id].length - 1];
            if (!lastOpt || Math.abs(lastOpt.y - yPos) > 1.0) {
                lookupY[st.id].push({ y: yPos, segId: segId }); 
                uniqueStations.push({ id: st.id, name: st.name, baseY: yPos, weight: st.weight || 0 });
            }
            if (relativeKm > segMaxKm) segMaxKm = relativeKm;
        });
        currentAccumulatedKm += segMaxKm; 
    });

    loopKm = currentAccumulatedKm;
    loopHeight = loopKm * CONFIG.scaleY;

    // ==========================================
    // 🌟 核心修復：把 initCanvas('diaCanvas', 'canvas-wrapper') 刪掉！
    // 畫布尺寸已經在 init() 和 resize() 處理好了，不准在這裡一直重設！
    // ==========================================
    
    const wrapper = document.getElementById('canvas-wrapper');
    const wrapperW = wrapper.clientWidth;
    const wrapperH = wrapper.clientHeight;

    const viewTop = camera.y - 100;
    const viewBottom = camera.y + wrapperH + 100; 
    const viewLeft = camera.x - 100;
    const viewRight = camera.x + wrapperW + 100;

    ctx.save();
    ctx.translate(-camera.x, -camera.y);

    // ... (下面維持你原本的畫橫線、畫時間標籤的迴圈邏輯) ...

    const { copyStart, copyEnd } = isCircular
        ? getCircularCopyRange(loopHeight, viewTop, viewBottom)
        : { copyStart: 0, copyEnd: 0 };

    for (let copy = copyStart; copy <= copyEnd; copy++) {
        let offsetY = isCircular ? ((copy * loopHeight) + CONFIG.paddingTop + loopHeight) : CONFIG.paddingTop;

        ctx.font = "bold 16px 'GlowSans', sans-serif";
        ctx.textBaseline = "middle";

        // ==========================================
        // 🌟 核心邏輯：全域排序與空間競爭 (Greedy Label Placement)
        // ==========================================
        // 1. 抓出畫面上的車站，並注入我們剛才算好的「全域權重」
        let labelCandidates = uniqueStations.map(st => {
            return {
                ...st,
                y: st.baseY + offsetY,
                weight: window.globalStationWeights[String(st.id)] || 0 
            };
        }).filter(st => st.y >= viewTop - 20 && st.y <= viewBottom + 20);

        // 2. 全域排序：權重由大到小！(確保含金量最高的大站優先處理)
        labelCandidates.sort((a, b) => (b.weight - a.weight) || (a.baseY - b.baseY));

        let drawnYList = [];
        const MIN_SPACING = 18; // 🌟 容許的最小垂直距離

        // 3. 依序放入：大站先選位，後面的小站如果發現位子被大站佔走(相撞)，就乖乖隱藏
        labelCandidates.forEach(cand => {
            let isCollision = drawnYList.some(drawnY => Math.abs(drawnY - cand.y) < MIN_SPACING);
            cand.showLabel = !isCollision; 
            if (!isCollision) {
                drawnYList.push(cand.y); 
            }
        });

        let showLabelMap = new Map(labelCandidates.map(c => [c.id, c.showLabel]));
        // ==========================================

        uniqueStations.forEach(st => {
            let y = st.baseY + offsetY;
            if (y < viewTop || y > viewBottom) return;

            // --- 畫背景橫線 (小站雖然字隱形，但橫線軌道還是要畫出來) ---
            if (layer === 'lines' || layer === 'all') {
                let isHovered = (st.id === hoveredStation);
                let isSelected = (st.id === selectedStation);

                if (isSelected) {
                    ctx.strokeStyle = "#FFD700";
                    ctx.lineWidth = 2.0;
                } else if (isHovered) {
                    ctx.strokeStyle = isDarkMode ? "#555555" : "#D0D0D0";
                    ctx.lineWidth = 1.5;
                } else {
                    ctx.strokeStyle = isDarkMode ? "#333333" : "#E0E0E0";
                    ctx.lineWidth = 1.0;
                }

                ctx.beginPath();
                ctx.moveTo(CONFIG.paddingLeft, y);
                ctx.lineTo(CONFIG.paddingLeft + (1560 * CONFIG.scaleX), y);
                ctx.stroke();
            }

            // --- 🌟 左右雙向懸浮站名 ---
            if (layer === 'labels' || layer === 'all') {
                
                // 🌟 檢查剛剛的生存戰，如果小站被大站擠掉了，就不印字直接跳過！
                if (showLabelMap.get(st.id) !== true) return;

                let maskBg = isDarkMode ? "rgba(0, 0, 0, 0.75)" : "rgba(255, 255, 255, 0.85)";
                let textColor = isDarkMode ? "#FFFFFF" : "#000000";
                let textWidth = ctx.measureText(st.name).width;

                // --- 左側站名 ---
                let labelXLeft = Math.max(0, camera.x + 10); 
                ctx.fillStyle = maskBg;
                ctx.fillRect(labelXLeft - 5, y - 12, textWidth + 10, 24);
                ctx.fillStyle = textColor;
                ctx.textAlign = "left";
                ctx.fillText(st.name, labelXLeft, y);

                // --- 右側站名（永遠在 viewport 右緣，與左側對稱）---
                let maxGridRight = CONFIG.paddingLeft + (1560 * CONFIG.scaleX) + 50; 
                let labelXRight = Math.min(camera.x + wrapperW - 10, maxGridRight);
                ctx.fillStyle = maskBg;
                ctx.fillRect(labelXRight - textWidth - 5, y - 12, textWidth + 10, 24);
                ctx.fillStyle = textColor;
                ctx.textAlign = "right";
                ctx.fillText(st.name, labelXRight, y);
            }
        });
    }

    ctx.font = "bold 18px 'GlowSans', sans-serif";
    ctx.textAlign = "center";

    // --- 🌟 上下雙向懸浮時間軸 (智慧邊界版) ---
    let routeStartY = CONFIG.paddingTop;
    let routeEndY = CONFIG.paddingTop + loopHeight;

    // 🌟 核心防護：限制垂直線不要畫到外太空！如果是短路線，線條就只畫到最後一站。
    let lineTop = isCircular ? viewTop : Math.max(viewTop, routeStartY - 20);
    let lineBottom = isCircular ? viewBottom : Math.min(viewBottom, routeEndY + 20);

    // ==========================================
    // 🌟 1. 智慧比例尺：根據目前的 X 軸縮放比例，決定時間文字的間距
    // ==========================================
    let textInterval = 60; // 預設每 60 分鐘標示一次
    
    // 如果 10 分鐘的物理像素寬度大於 60px，代表放得夠大，可以每 10 分鐘印一次！
    if (CONFIG.scaleX * 10 > 60) {
        textInterval = 10;
    } 
    // 如果稍微放大，容納得下 30 分鐘的間隔，就印 30 分鐘
    else if (CONFIG.scaleX * 30 > 50) {
        textInterval = 30;
    }

    for (let m = 0; m <= 1560; m += 10) {
        let x = timeToX(m);
        if (x < viewLeft - 50 || x > viewRight + 50) continue; 

        let isHourLine = (m % 60 === 0);

        // --- 畫背景直線 ---
        if (layer === 'lines' || layer === 'all') {
            ctx.beginPath();
            if (isHourLine) {
                ctx.strokeStyle = isDarkMode ? "#888888" : "#777777";
                ctx.lineWidth = 2.0;
            } else {
                ctx.setLineDash([3, 5]);
                ctx.strokeStyle = isDarkMode ? "#444444" : "#DDDDDD";
                ctx.lineWidth = 1.2;
            }

            ctx.moveTo(x, lineTop);                 
            ctx.lineTo(x, lineBottom);     
            ctx.stroke();
            ctx.setLineDash([]); 
        }

        // --- 🌟 上下時間標籤 ---
        if (layer === 'labels' || layer === 'all') {
            
            // 🌟 2. 判斷這個分鐘數是否符合我們算好的間距 (textInterval)
            if (m % textInterval === 0) {
                
                let displayHour = Math.floor(m / 60);
                let displayMin = m % 60;
                
                // 格式化時間 (例如 17:00, 17:10)
                let mm = displayMin.toString().padStart(2, '0');
                let timeStr = `${displayHour}:${mm}`;
                
                // 🌟 3. 視覺層次區分：整點字體大一點，十分鐘字體稍微小一點
                if (isHourLine) {
                    ctx.font = "bold 18px 'GlowSans', sans-serif";
                } else {
                    ctx.font = "bold 14px 'GlowSans', sans-serif";
                }
                
                let textColor = isDarkMode ? "#FFFFFF" : "#000000";

                let labelYTop = isCircular ? Math.max(CONFIG.paddingTop - 25, camera.y + 30) : Math.max(routeStartY - 25, Math.min(camera.y + 30, routeEndY));
                let labelYBottom = isCircular ? camera.y + wrapperH - 30 : Math.min(camera.y + wrapperH - 30, routeEndY + 30);

                ctx.textAlign = "center";      
                ctx.textBaseline = "middle";   
                ctx.lineWidth = 4;             
                ctx.strokeStyle = isDarkMode ? "#000000" : "#FFFFFF"; 

                // 畫頂部
                ctx.strokeText(timeStr, x, labelYTop);  
                ctx.fillStyle = textColor;
                ctx.fillText(timeStr, x, labelYTop);    

                // 畫底部
                ctx.strokeText(timeStr, x, labelYBottom); 
                ctx.fillStyle = textColor;
                ctx.fillText(timeStr, x, labelYBottom);   
            }
        }
    }
    ctx.restore(); 
}

// ==========================================
// 🌟 嚴謹尋路器：嚴格綁定 Line ID，拒絕張冠李戴
// ==========================================
function getJunction(st1_id, st2_id, line1_id, line2_id) {
    let cacheKey = `${st1_id}-${st2_id}-${line1_id}-${line2_id}`;
    if (junctionCache[cacheKey] !== undefined) return junctionCache[cacheKey];

    let seg1 = topology.segments.find(s => s.id === line1_id);
    let seg2 = topology.segments.find(s => s.id === line2_id);
    if (!seg1 || !seg2) return null;

    // 1. 尋找「直接交會站」
    let ids1 = seg1.stations.map(st => st.id);
    let junc = seg2.stations.find(st => ids1.includes(st.id));
    if (junc) {
        let result = { type: 'direct', id: junc.id };
        junctionCache[cacheKey] = result;
        return result;
    }

    // 2. 尋找 1-Hop 橋接路線 (例如 名古屋線 -> [大阪線] -> 難波線)
    for (let bridge of topology.segments) {
        if (bridge.id === line1_id || bridge.id === line2_id) continue;
        
        let bridgeIds = bridge.stations.map(st => st.id);

        let junc1 = seg1.stations.find(st => bridgeIds.includes(st.id));
        let junc2 = seg2.stations.find(st => bridgeIds.includes(st.id));

        if (junc1 && junc2) {
            let result = { type: 'bridge', line: bridge.id, junc1: junc1.id, junc2: junc2.id };
            junctionCache[cacheKey] = result;
            return result;
        }
    }

    junctionCache[cacheKey] = null;
    return null;
}

// ==========================================
// 繪製火車 (全域智慧連線版)
// ==========================================
function drawTrains() {
    const wrapper = document.getElementById('canvas-wrapper');
    const viewTop = camera.y - 200;
    const viewBottom = camera.y + canvas.clientHeight + 200;
    const viewLeft = camera.x - 200;
    const viewRight = camera.x + canvas.clientWidth + 200;

    let presetKey = currentRouteView; 
    let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
    const { copyStart, copyEnd } = isCircular
        ? getCircularCopyRange(loopHeight, viewTop, viewBottom)
        : { copyStart: 0, copyEnd: 0 };

    let colorIndex = isDarkMode ? 0 : 1;
    let fallbackColor = isDarkMode ? "#FFFFFF" : "#000000";

    const drawnCoupledSegments = new Set();

    ctx.save();
    ctx.translate(-camera.x, -camera.y);

    ctx.beginPath();
    let startX = CONFIG.paddingLeft;
    let endX = timeToX(1560); // 26小時邊界
    ctx.rect(startX, -50000, endX - startX, 100000); 
    ctx.clip(); // 喀嚓！限制火車只在 0:00~26:00 內畫圖，上下無限延伸

    // 🌟 注意：這裡不要有任何 ctx.save() 或 ctx.translate()！
    // 直接緊接著宣告 drawSingleTrain
    const drawSingleTrain = (train, isVIP, isHovered, isPartner = false) => {
        // ==========================================
        // 🌟 1. 先決定這台車「原本的」顏色和粗細
        // ==========================================
        let baseColor = fallbackColor;
        let baseWidth = train.w || 1.5; // 通用的保底粗細 (如果設定檔沒寫，預設 1.5)

        let _tc = getTrainColorValue(train.type);
        if (_tc) {
            let typeStyle = _tc;
            baseColor = typeStyle[colorIndex]; // 抓取顏色 (深色/淺色模式)
            
            // 🌟 終極通用解法：如果有設定第三個參數，就把它當作該車種的專屬粗細！
            if (typeStyle.length > 2) {
                baseWidth = typeStyle[2];
            }
        }

        let trainColor = baseColor;
        let lineWidth = baseWidth;

        // ==========================================
        // 🌟 2. 再根據狀態換衣服 (這時候 baseColor 已經準備好了)
        // ==========================================
        if (isVIP || isPartner) {
            trainColor = '#FFD700'; // 🌟 點擊的主角：亮黃色
            lineWidth = 4.0;
        } else if (isHovered) {
            let adjustAmount = isDarkMode ? 70 : -50; 
            // 這裡就不會再報 baseColor is not defined 囉！
            trainColor = adjustBrightness(baseColor, adjustAmount); 
            lineWidth = baseWidth; 
        }

        // 3. 把算好的顏色交給畫筆
        ctx.strokeStyle = trainColor; 
        ctx.lineWidth = lineWidth;

        // 4. 無條件清空麵包屑袋子
        // 🌟 優化 3：重複利用陣列，不重新要記憶體空間！
        if (!train._hitPoints) {
            train._hitPoints = [];
        }
        train._hitPoints.length = 0; // 這樣可以清空陣列，但不會產生垃圾！ 

        // 🚀 視口剔除：整車時間範圍完全在畫面左右之外時，直接跳過昂貴的座標運算與繪製。
        // （大型路線如 JR西日本 數千班車，縮放時可避免每幀為離畫面的車重算座標 → 大幅減卡頓）
        if (!isVIP && !isHovered && !isPartner && train.segments && train.segments.length) {
            let _segs = train.segments;
            let _lastSeg = _segs[_segs.length - 1];
            let _t0 = _segs[0].t[0];
            let _t1 = _lastSeg.t[_lastSeg.t.length - 1];
            if (_t0 != null && _t1 != null) {
                let _xa = timeToX(Math.min(_t0, _t1));
                let _xb = timeToX(Math.max(_t0, _t1));
                if (_xb < viewLeft || _xa > viewRight) return;
            }
        }

        let trainLastBaseY = null;
        let wrapOffset = 0;
        
        // ... (下面接續你原本的座標計算跟撒麵包屑邏輯) ...

        // 👉 下面這整段是你原本超厲害的座標運算，完全沒變！
        train.segments.forEach((seg, segIdx) => {
            let unwrappedCoords = [];
            for (let i = 0; i < seg.s.length; i++) {
                let st_id = seg.s[i];
                let options = lookupY[st_id];
                if (!options || options.length === 0) { unwrappedCoords.push(null); continue; }

                let matchedOpt = options.find(opt => opt.segId === seg.id);
                let baseY = options[0].y; 
                if (matchedOpt) {
                    baseY = matchedOpt.y;
                } else if (trainLastBaseY !== null && options.length > 1) {
                    let minDist = Infinity;
                    options.forEach(opt => {
                        let dist = Math.abs(opt.y - trainLastBaseY);
                        if (dist < minDist) { minDist = dist; baseY = opt.y; }
                    });
                }

                if (trainLastBaseY !== null && isCircular) {
                    let dy = baseY - trainLastBaseY;
                    if (dy > loopHeight / 2) wrapOffset -= loopHeight; 
                    else if (dy < -loopHeight / 2) wrapOffset += loopHeight; 
                }
                
                unwrappedCoords.push(baseY + wrapOffset);
                trainLastBaseY = baseY;
            }

            let minX = timeToX(seg.t[0]);
            let maxX = timeToX(seg.t[seg.t.length - 1]);

            for (let copy = copyStart; copy <= copyEnd; copy++) {
                let offsetY = isCircular ? ((copy * loopHeight) + CONFIG.paddingTop + loopHeight) : CONFIG.paddingTop;
                
                let minY = Infinity, maxY = -Infinity;
                for (let i = 0; i < unwrappedCoords.length; i++) {
                    if (unwrappedCoords[i] !== null) {
                        let y = unwrappedCoords[i] + offsetY;
                        if (y < minY) minY = y;
                        if (y > maxY) maxY = y;
                    }
                }

                if (maxX < viewLeft || minX > viewRight || maxY < viewTop || minY > viewBottom) continue; 
                
                ctx.save(); 
                // (我們已經在最外層設定了完美的左右裁切，這裡不需要再拿剪刀了，直接畫！)

                ctx.beginPath();
                let isDrawing = false;

                // ==========================================
                // 🌟🌟🌟 新增這行：只要畫布起了一個新的頭，麵包屑就強制斷開！避免產生隱形連線！
                // ==========================================
                train._hitPoints.push(null);

                // ==========================================
                // 【第一階段：畫主實線】(絕對忠於自己的時間，絕不互相等待)
                // ==========================================
                for (let i = 0; i < seg.s.length; i++) {
                    let y_raw = unwrappedCoords[i];
                    if (y_raw === null) { 
                        isDrawing = false; 
                        train._hitPoints.push(null); 
                        continue; 
                    }

                    let y = y_raw + offsetY; 
                    let x_arr = timeToX(seg.t[i * 2]);
                    let x_dep = timeToX(seg.t[i * 2 + 1]);

                    // 把算好的真實座標存起來 (麵包屑)
                    train._hitPoints.push({ x: x_arr, y: y });
                    if (seg.v[i] !== 2) {
                        train._hitPoints.push({ x: x_dep, y: y });
                    }

                    if (!isDrawing) { 
                        if (i === 0 && segIdx > 0) {
                            ctx.moveTo(x_dep, y); // 新路段從自己的離站點出發！
                        } else {
                            ctx.moveTo(x_arr, y); 
                        }
                        isDrawing = true; 
                    } else { 
                        ctx.lineTo(x_arr, y); 
                    }

                    // 畫自己的停靠水平線
                    if (seg.v[i] !== 2) {
                        ctx.lineTo(x_dep, y); 
                    }
                }
                ctx.stroke(); // 實線畫完，提筆！

                // ==========================================
                // 🌟🌟🌟 新增 A：精準疊加雙色虛線 (回歸物理真理版)
                // ==========================================
                if (train.coupled_with && !isVIP && !isPartner) {
                    let coupledInfos = train.coupled_with.filter(c => c.action === "split" || c.action === "merge");
                    
                    coupledInfos.forEach(cInfo => {
                        let partner = timetable.find(t => String(t.no || t.train_no || t.id) === String(cInfo.train_id));

                        if (partner && partner.segments && partner.segments.length > 0) {
                            let pColor = fallbackColor;
                            let _ptc = getTrainColorValue(partner.type);
                            if (_ptc) pColor = _ptc[colorIndex];

                            let myStations = [];
                            train.segments.forEach(tSeg => {
                                tSeg.s.forEach(id => myStations.push(String(id)));
                            });

                            let splitStation = String(cInfo.station_id);
                            let splitIdx = myStations.indexOf(splitStation);
                            
                            if (splitIdx !== -1) {
                                let coupledDirection = (cInfo.action === 'split') ? 'before' : 'after';

                                ctx.save();
                                ctx.beginPath();
                                let isDrawingDash = false;

                                for (let i = 0; i < seg.s.length; i++) {
                                    let stId = String(seg.s[i]);
                                    let y_raw = unwrappedCoords[i];
                                    
                                    if (y_raw === null) { 
                                        isDrawingDash = false; 
                                        continue; 
                                    }
                                    
                                    let y = y_raw + offsetY;
                                    let myArr = seg.t[i * 2];
                                    let myDep = seg.t[i * 2 + 1];
                                    let x_arr = timeToX(myArr);
                                    let x_dep = timeToX(myDep);

                                    let currentIdx = myStations.indexOf(stId);
                                    let isCoupledRegion = false;

                                    if (coupledDirection === 'before') {
                                        isCoupledRegion = (currentIdx <= splitIdx);
                                    } else if (coupledDirection === 'after') {
                                        isCoupledRegion = (currentIdx >= splitIdx);
                                    }

                                    if (isCoupledRegion) {
                                        // --- 畫虛線的「到站」段 ---
                                        if (myArr !== null) {
                                            if (coupledDirection === 'after' && stId === splitStation) {
                                                isDrawingDash = false; 
                                            } else {
                                                if (!isDrawingDash) {
                                                    ctx.moveTo(x_arr, y);
                                                    isDrawingDash = true;
                                                } else {
                                                    ctx.lineTo(x_arr, y);
                                                }
                                            }
                                        }
                                        
                                        // --- 畫虛線的「停靠」段 ---
                                        if (seg.v[i] !== 2 && myDep !== null) {
                                            if (coupledDirection === 'before' && stId === splitStation) {
                                                // 🌟 分岔站特判：虛線只能畫到「第一台車離開」的瞬間！
                                                let pDep = myDep; 
                                                if (partner.segments) {
                                                    let pSeg = partner.segments.find(s => s.s.map(String).includes(stId));
                                                    if (pSeg) {
                                                        let pIdx = pSeg.s.findIndex(sid => String(sid) === stId);
                                                        pDep = pSeg.t[pIdx * 2 + 1];
                                                    }
                                                }
                                                // 誰先發車就取誰的時間 (Math.min)
                                                let splitTime = Math.min(myDep, pDep !== undefined && pDep !== null ? pDep : myDep);
                                                let x_split = timeToX(splitTime);

                                                if (!isDrawingDash) {
                                                    ctx.moveTo(x_split, y);
                                                    isDrawingDash = true;
                                                } else {
                                                    ctx.lineTo(x_split, y);
                                                }
                                                isDrawingDash = false; // 畫完共用等待時間後，正式切斷虛線！
                                            } else {
                                                if (!isDrawingDash) {
                                                    ctx.moveTo(x_dep, y);
                                                    isDrawingDash = true;
                                                } else {
                                                    ctx.lineTo(x_dep, y);
                                                }
                                            }
                                        }
                                    } else {
                                        isDrawingDash = false;
                                    }
                                }

                                ctx.strokeStyle = pColor;
                                ctx.lineWidth = lineWidth + 0.8; 
                                ctx.setLineDash([12, 12]);
                                ctx.stroke();
                                ctx.restore();
                            }
                        }
                    });
                }

                // ==========================================
                // 🌟🌟🌟 新增 B：畫出水平短虛線 (直通接駁特效)
                // ==========================================
                // 確保這是在火車的「最後一個路段」才檢查
                if (train.coupled_with && segIdx === train.segments.length - 1) {
                    let directInfo = train.coupled_with.find(c => c.action === "direct");
                    if (directInfo) {
                        let nextTrain = timetable.find(t => t.no === directInfo.train_id);
                        if (nextTrain && nextTrain.segments.length > 0) {
                            
                            // 抓這台車的「最後一站」跟下一台車的「第一站」
                            let lastI = seg.s.length - 1;
                            let currentLastStationId = seg.s[lastI];
                            let nextFirstStationId = nextTrain.segments[0].s[0];
                            
                            // 🌟 修正：不比對中文站名，直接比對拓樸的車站 ID (例如 THK18 === THK18)
                            if (currentLastStationId === nextFirstStationId) {
                                let endY_raw = unwrappedCoords[lastI];
                                let endY = endY_raw !== null ? endY_raw + offsetY : null;

                                let endT = seg.t[lastI * 2 + 1];
                                if (endT === "" || endT === undefined) endT = seg.t[lastI * 2];
                                let endX = timeToX(endT);

                                let nextSeg = nextTrain.segments[0];
                                let startT = nextSeg.t[0];
                                if (startT === "" || startT === undefined) startT = nextSeg.t[1];
                                let startX = timeToX(startT);

                                // 確保座標有效，且時間是向後走的，才畫出接駁虛線
                                if (!isNaN(endX) && !isNaN(startX) && startX >= endX && endY !== null) {
                                    ctx.save();
                                    ctx.beginPath();
                                    ctx.moveTo(endX, endY);
                                    ctx.lineTo(startX, endY);
                                    
                                    ctx.strokeStyle = trainColor; // 延續自己原本的顏色
                                    ctx.setLineDash([]); 
                                    ctx.lineWidth = lineWidth; 
                                    ctx.stroke();
                                    ctx.restore();
                                }
                            }
                        }
                    }
                }

                // ==========================================
                // 🌟🌟🌟 新增 C：併結匯合的水平等待線
                // 本車抵達匯合站(如紀州路快速→日根野 08:28)後，與後段(関空快速 08:33 出發)之間
                // 因兩車時間不同會留下空隙，補上一段水平線銜接，避免列車看起來斷開。
                // ==========================================
                if (train.coupled_with && segIdx === train.segments.length - 1) {
                    let mergeInfo = train.coupled_with.find(c => c.action === "merge");
                    if (mergeInfo) {
                        let partner = timetable.find(t => String(t.no || t.train_no || t.id) === String(mergeInfo.train_id));
                        let lastI = seg.s.length - 1;
                        let junctionId = String(seg.s[lastI]);

                        // 交會站必須是本車終點站，且與 coupled_with 記錄的匯合站一致
                        if (partner && partner.segments && partner.segments.length > 0 &&
                            String(mergeInfo.station_id) === junctionId) {

                            // partner 在交會站的離站時間（取最後一次出現，即繼續向後行駛的那段）
                            let partnerDep = null;
                            partner.segments.forEach(ps => {
                                let pIdx = ps.s.findIndex(sid => String(sid) === junctionId);
                                if (pIdx !== -1) {
                                    let d = ps.t[pIdx * 2 + 1];
                                    let a = ps.t[pIdx * 2];
                                    partnerDep = (d !== undefined && d !== null && d !== "") ? d : a;
                                }
                            });

                            let myArr = seg.t[lastI * 2];
                            if (myArr === null || myArr === undefined || myArr === "") myArr = seg.t[lastI * 2 + 1];
                            let endY = unwrappedCoords[lastI] !== null ? unwrappedCoords[lastI] + offsetY : null;

                            if (endY !== null && partnerDep !== null && myArr !== null && myArr !== undefined && myArr !== "") {
                                let startX = timeToX(myArr);
                                let endX = timeToX(partnerDep);
                                if (!isNaN(startX) && !isNaN(endX) && endX >= startX) {
                                    ctx.save();
                                    ctx.beginPath();
                                    ctx.moveTo(startX, endY);
                                    ctx.lineTo(endX, endY);
                                    ctx.strokeStyle = trainColor; // 延續自己原本的顏色
                                    ctx.setLineDash([]);
                                    ctx.lineWidth = lineWidth;
                                    ctx.stroke();
                                    ctx.restore();
                                }
                            }
                        }
                    }
                }

                // 🌟 3. 放下剪刀！讀取剛剛的存檔 (畫布恢復成無限大)
                ctx.restore();

                // ==========================================
                // 畫 VIP 車次的專屬字體
                if (isVIP || isPartner) {
                    ctx.save(); 

                    for (let i = 0; i < seg.s.length; i++) {
                        let y_raw = unwrappedCoords[i];
                        if (y_raw === null) continue; // 遇到斷點跳過

                        if (seg.v[i] === 2) continue; // 通過站不印字
                        
                        let y = y_raw + offsetY;
                        let arrT = seg.t[i * 2];
                        let depT = seg.t[i * 2 + 1];
                        let x_dep = timeToX(depT); // 出站的 X 座標
                        let x_arr = timeToX(arrT); // 抵達的 X 座標

                        // 🌟 1. 定義畫布的絕對邊界 (0:00 ~ 26:00)
                        let leftBoundary = CONFIG.paddingLeft;
                        let rightBoundary = CONFIG.paddingLeft + (1560 * CONFIG.scaleX);

                        // 🌟 2. 邊界過濾：如果抵達時間在右邊界之外，或是發車時間在左邊界之外，就直接隱形！
                        if (x_arr > rightBoundary || x_dep < leftBoundary) {
                            continue; 
                        }

                        // --- 3. 準備文字：站名與時間 ---
                        let stationName = getStationName(seg.s[i]);

                        // 🌟 1. 基礎直通時間修補
                        // ==========================================
                        // 🌟 修正：畫布文字也必須加入終點站與起點站的嚴格驗證
                        // ==========================================
                        let trLastSeg = train.segments[train.segments.length - 1];
                        let trLastSt = String(trLastSeg.s[trLastSeg.s.length - 1]);
                        let trFirstSt = String(train.segments[0].s[0]);

                        let isDirectOut = (segIdx === train.segments.length - 1 && i === seg.s.length - 1 &&
                            train.coupled_with && train.coupled_with.some(c => c.action === "direct" && String(c.station_id) === trLastSt &&
                                timetable.some(t => String(t.no || t.train_no || t.id) === String(c.train_id))));

                        let isDirectIn = (segIdx === 0 && i === 0 &&
                            train.coupled_with && train.coupled_with.some(c => c.action === "direct" && String(c.station_id) === trFirstSt &&
                                timetable.some(t => String(t.no || t.train_no || t.id) === String(c.train_id))));

                        // 環狀列車（trFirstSt === trLastSt）的起點/終點不套用直通時間覆寫
                        const isCircularTrain = (trFirstSt === trLastSt);

                        // 輔助函式：判斷某班車是否為環狀
                        const _checkPartnerCircular = (partnerTrain) => {
                            if (!partnerTrain || !partnerTrain.segments || partnerTrain.segments.length === 0) return false;
                            const pFirst = String(partnerTrain.segments[0].s[0]);
                            const pLastSeg = partnerTrain.segments[partnerTrain.segments.length - 1];
                            return pFirst === String(pLastSeg.s[pLastSeg.s.length - 1]);
                        };

                        if (isDirectOut && !isCircularTrain) {
                            let dInfo = train.coupled_with.find(c => c.action === "direct" && String(c.station_id) === trLastSt);
                            let nxt = dInfo && timetable.find(t => String(t.no || t.train_no || t.id) === String(dInfo.train_id));
                            // partner 是環狀代表只是「同一地點車次接續」，不覆寫時間
                            if (nxt && !_checkPartnerCircular(nxt) && nxt.segments[0]) {
                                let nt = nxt.segments[0].t;
                                depT = (nt[1] !== undefined && nt[1] !== null && nt[1] !== "") ? nt[1] : nt[0];
                                x_dep = timeToX(depT);
                            }
                        } else if (isDirectIn && !isCircularTrain) {
                            let dInfo = train.coupled_with.find(c => c.action === "direct" && String(c.station_id) === trFirstSt);
                            let prv = dInfo && timetable.find(t => String(t.no || t.train_no || t.id) === String(dInfo.train_id));
                            if (prv && !_checkPartnerCircular(prv) && prv.segments[prv.segments.length - 1]) {
                                let pt = prv.segments[prv.segments.length - 1].t;
                                let lastK = prv.segments[prv.segments.length - 1].s.length - 1;
                                arrT = (pt[lastK * 2] !== undefined && pt[lastK * 2] !== null && pt[lastK * 2] !== "") ? pt[lastK * 2] : pt[lastK * 2 + 1];
                                x_arr = timeToX(arrT);
                            }
                        }

                        let finalArrStr = formatTimeDisplay(arrT);
                        let finalDepStr = formatTimeDisplay(depT);
                        let displayText = "";
                        
                        // 🌟🌟🌟 核心修復：把排版變數拉到「最外層宣告」，這樣後面的畫布才抓得到！
                        let familyAlign = 'left';
                        let familyDrawX = x_dep;
                        let familyFallbackX = x_arr;

                        // ==========================================
                        // 🌟 2. 終極發言權判定機制
                        // ==========================================
                        let isDesignatedSpeaker = false;

                        if (isVIP) {
                            // 環狀列車（起站 == 終站）的末站：isDirectOut=true 但時間不覆寫，正常顯示
                            // 本身是環狀，或 partner 是環狀（只是車次接續），終點標籤照常顯示
                            const _nxtForCheck = isDirectOut && (() => {
                                let di = train.coupled_with && train.coupled_with.find(c => c.action === "direct" && String(c.station_id) === trLastSt);
                                return di && timetable.find(t => String(t.no || t.train_no || t.id) === String(di.train_id));
                            })();
                            if (!isDirectOut || isCircularTrain || _checkPartnerCircular(_nxtForCheck)) isDesignatedSpeaker = true;
                        } else if (isPartner && typeof selectedTrain !== 'undefined' && selectedTrain) {
                            let vipPresentHere = selectedTrain.segments.some(s => s.s.map(String).includes(String(seg.s[i])));

                            if (!vipPresentHere) {
                                // 若這是伴侶車的直通終站，讓後繼直通車統一印標籤，避免重複
                                let isPartnerDirectOutHere = (
                                    segIdx === train.segments.length - 1 && i === seg.s.length - 1 &&
                                    train.coupled_with &&
                                    train.coupled_with.some(c => c.action === "direct" && String(c.station_id) === String(seg.s[i]))
                                );
                                if (!isPartnerDirectOutHere) isDesignatedSpeaker = true;
                            } else {
                                // VIP 也停同一站，但若時間差距 > 10 分鐘，代表是不同時刻的過站
                                // （如 4237 在 22:00 出發天王寺，4237M 在 22:41 過天王寺），應各自顯示標籤
                                let myTime = seg.t[i * 2];
                                let vipTimeAtStation = null;
                                const stIdStr = String(seg.s[i]);
                                for (let vs of selectedTrain.segments) {
                                    let idx = vs.s.findIndex(id => String(id) === stIdStr);
                                    if (idx !== -1) { vipTimeAtStation = vs.t[idx * 2]; break; }
                                }
                                if (typeof myTime === 'number' && typeof vipTimeAtStation === 'number'
                                    && Math.abs(myTime - vipTimeAtStation) > 10) {
                                    // 若這是伴侶車的直通終站，VIP 會以 isDirectIn 模式畫合併標籤，此處讓出發言權
                                    let isPartnerDirectOutHere = (
                                        segIdx === train.segments.length - 1 && i === seg.s.length - 1 &&
                                        train.coupled_with &&
                                        train.coupled_with.some(c => c.action === "direct" && String(c.station_id) === String(seg.s[i]))
                                    );
                                    if (!isPartnerDirectOutHere) isDesignatedSpeaker = true;
                                } else {
                                    let vipLastSeg = selectedTrain.segments[selectedTrain.segments.length - 1];
                                    let vipLastSt = vipLastSeg.s[vipLastSeg.s.length - 1];
                                    if (String(vipLastSt) === String(seg.s[i])) {
                                        let vipDirectsToMe = selectedTrain.coupled_with && selectedTrain.coupled_with.some(c =>
                                            c.action === "direct" && String(c.train_id) === String(train.no || train.train_no || train.id)
                                        );
                                        if (vipDirectsToMe) isDesignatedSpeaker = true;
                                    }
                                }
                            }
                        }

                        else if (!selectedTrain) {
                            // 🌟 核心修復 3：如果畫布上什麼都沒點，大家都有發言權！
                            isDesignatedSpeaker = true;
                        }

                        // ==========================================
                        // 🌟 3. 只有拿到麥克風的人，才能進行字串推論組合！
                        // ==========================================
                        if (isDesignatedSpeaker) {
                            let myFamily = [];
                            if (typeof vipTrain !== 'undefined' && vipTrain) myFamily.push(vipTrain);
                            if (typeof partnerTrains !== 'undefined') myFamily.push(...partnerTrains);

                            let splitTrainA = null;
                            let splitTrainB = null;

                            for (let ft of myFamily) {
                                if (ft.coupled_with) {
                                    let sInfo = ft.coupled_with.find(c => (c.action === "split" || c.action === "merge") && String(c.station_id) === String(seg.s[i]));
                                    if (sInfo) {
                                        splitTrainA = ft;
                                        splitTrainB = timetable.find(t => String(t.no || t.train_no || t.id) === String(sInfo.train_id));
                                        break; 
                                    }
                                }
                            }

                            if (splitTrainA && splitTrainB) {
                                // 🌟 尋找終點站 (自動往後追蹤直通)
                                const getFinalDest = (tObj) => {
                                    let curr = tObj;
                                    let visited = new Set([String(curr.no || curr.train_no || curr.id)]);
                                    while(true) {
                                        let dInfo = curr.coupled_with ? curr.coupled_with.find(cx => cx.action === "direct") : null;
                                        if(dInfo) {
                                            let nxt = timetable.find(tx => String(tx.no || tx.train_no || tx.id) === String(dInfo.train_id));
                                            if (nxt && !visited.has(String(nxt.no || nxt.train_no || nxt.id))) {
                                                visited.add(String(nxt.no || nxt.train_no || nxt.id)); curr = nxt;
                                            } else break;
                                        } else break;
                                    }
                                    let lSeg = curr.segments[curr.segments.length-1];
                                    return getStationName(lSeg.s[lSeg.s.length-1]);
                                };
                                
                                // 🌟 尋找起點站 (自動往回追蹤直通)
                                const getOrigin = (tObj) => {
                                    let curr = tObj;
                                    let visited = new Set([String(curr.no || curr.train_no || curr.id)]);
                                    while(true) {
                                        let isDIn = curr.coupled_with && curr.coupled_with.some(cx => cx.action === "direct" && String(curr.segments[0].s[0]) === String(cx.station_id));
                                        if (isDIn) {
                                            let dInfo = curr.coupled_with.find(cx => cx.action === "direct" && String(curr.segments[0].s[0]) === String(cx.station_id));
                                            let prev = timetable.find(tx => String(tx.no || tx.train_no || tx.id) === String(dInfo.train_id));
                                            if (prev && !visited.has(String(prev.no || prev.train_no || prev.id))) {
                                                visited.add(String(prev.no || prev.train_no || prev.id));
                                                curr = prev;
                                            } else break;
                                        } else break;
                                    }
                                    return getStationName(curr.segments[0].s[0]);
                                };

                                // 🌟 智慧時間萃取器
                                const extInfo = (tObj) => {
                                let arr = null, dep = null;
                                
                                // 🌟 新增：找出該車次的絕對頭尾站
                                let objLastSeg = tObj.segments[tObj.segments.length - 1];
                                let objLastSt = String(objLastSeg.s[objLastSeg.s.length - 1]);
                                let objFirstSt = String(tObj.segments[0].s[0]);

                                for (let s of tObj.segments) {
                                    let idx = s.s.findIndex(id => String(id) === String(seg.s[i]));
                                    if (idx !== -1) {
                                        arr = (s.t[idx*2] !== undefined && s.t[idx*2] !== null && s.t[idx*2] !== "") ? s.t[idx*2] : null;
                                        dep = (s.t[idx*2+1] !== undefined && s.t[idx*2+1] !== null && s.t[idx*2+1] !== "") ? s.t[idx*2+1] : null;
                                        if(arr === null && dep !== null) arr = dep; 
                                        if(dep === null && arr !== null) dep = arr; 

                                        // ==========================================
                                        // 🌟 加入 objLastSt 驗證 (修復提前觸發 Bug)
                                        // 將 idx === s.s.length - 1 改為嚴格比對絕對站名！
                                        // ==========================================
                                        let isDOut = (String(seg.s[i]) === objLastSt && tObj.coupled_with && tObj.coupled_with.some(c => c.action === "direct" && String(c.station_id) === objLastSt));
                                        if (isDOut) {
                                            let dInfo = tObj.coupled_with.find(c => c.action === "direct" && String(c.station_id) === objLastSt);
                                            let nxt = timetable.find(tx => String(tx.no || tx.train_no || tx.id) === String(dInfo.train_id));
                                            if (nxt && nxt.segments[0]) {
                                                let nt = nxt.segments[0].t;
                                                let nDep = (nt[1] !== undefined && nt[1] !== null && nt[1] !== "") ? nt[1] : nt[0];
                                                if (nDep !== null) dep = nDep;
                                            }
                                        }

                                        // ==========================================
                                        // 🌟 加入 objFirstSt 驗證 (修復提前觸發 Bug)
                                        // 將 idx === 0 改為嚴格比對絕對站名！
                                        // ==========================================
                                        let isDIn = (String(seg.s[i]) === objFirstSt && tObj.coupled_with && tObj.coupled_with.some(c => c.action === "direct" && String(c.station_id) === objFirstSt));
                                        if (isDIn) {
                                            let dInfo = tObj.coupled_with.find(c => c.action === "direct" && String(c.station_id) === objFirstSt);
                                            let prv = timetable.find(tx => String(tx.no || tx.train_no || tx.id) === String(dInfo.train_id));
                                            if (prv && prv.segments[prv.segments.length-1]) {
                                                let pt = prv.segments[prv.segments.length-1].t;
                                                let lK = prv.segments[prv.segments.length-1].s.length - 1;
                                                let pArr = (pt[lK*2] !== undefined && pt[lK*2] !== null && pt[lK*2] !== "") ? pt[lK*2] : pt[lK*2+1];
                                                if (pArr !== null) arr = pArr;
                                            }
                                        }
                                        break;
                                    }
                                }
                                return { arr, dep, dest: getFinalDest(tObj), origin: getOrigin(tObj) };
                            };

                                let iA = extInfo(splitTrainA);
                                let iB = extInfo(splitTrainB);


                                // ==========================================
                                // 🌟 修復 1：避開 JavaScript「0 是 falsy」的陷阱
                                // ==========================================
                                let minArr = Math.min(iA.arr ?? Infinity, iB.arr ?? Infinity);
                                let maxDep = Math.max(iA.dep ?? -Infinity, iB.dep ?? -Infinity);

                                // ==========================================
                                // 🌟 終極判斷：實體端點與時間差雙重驗證引擎
                                // ==========================================
                                let isJoin = false;
                                
                                let stA = splitTrainA.segments.flatMap(s => s.s).map(String);
                                let stB = splitTrainB.segments.flatMap(s => s.s).map(String);
                                let currentStId = String(seg.s[i]);
                                let idxA = stA.indexOf(currentStId);
                                let idxB = stB.indexOf(currentStId);

                                const hasDirect = (tObj) => tObj.coupled_with && tObj.coupled_with.some(c => c.action === "direct");

                                let isRealEndA = (idxA === stA.length - 1) && !hasDirect(splitTrainA);
                                let isRealEndB = (idxB === stB.length - 1) && !hasDirect(splitTrainB);
                                let isRealStartA = (idxA === 0) && !hasDirect(splitTrainA);
                                let isRealStartB = (idxB === 0) && !hasDirect(splitTrainB);

                                if (isRealEndA || isRealEndB) {
                                    isJoin = true;  
                                } else if (isRealStartA || isRealStartB) {
                                    isJoin = false; 
                                } else {
                                    isJoin = (iA.arr !== iB.arr); 
                                }

                                if (isJoin) {
                                    // 🚄 【匯合模式 JOIN】 
                                    let joins = [
                                        { t: iA.arr, str: `${formatTimeDisplay(iA.arr)}(${iA.origin})` },
                                        { t: iB.arr, str: `${formatTimeDisplay(iB.arr)}(${iB.origin})` }
                                    ].sort((a,b) => (a.t || 0) - (b.t || 0));
                                    
                                    let sharedDep = maxDep !== -Infinity ? maxDep : (iA.dep || iB.dep);
                                    displayText = `${joins[0].str}/${joins[1].str}-${formatTimeDisplay(sharedDep)} ${stationName}`;

                                    // 🌟 修復 2：解決「跑到很右邊」的問題！
                                    // 最佳視覺解法：改回 right-align，但「錨點設在 maxDep (離開時間)」！
                                    // 這樣文字會從離開時間「往回寫」，剛好蓋在兩台車匯合的 V 型空間上方。
                                    familyAlign = 'right'; 
                                    if (maxDep !== -Infinity) familyDrawX = timeToX(maxDep);
                                    if (minArr !== Infinity) familyFallbackX = timeToX(minArr);
                                    
                                    // 🌟 更新外圍已經宣告好的變數 (直接覆寫值，不要加 let！)
                                    // JOIN：left-align 從出發時間往右延伸，與 SPLIT 對稱
                                    // （right-align 會因標籤過長而延伸到抵達時間之前，位置偏左）
                                    familyAlign = 'left';
                                    if (maxDep !== -Infinity) familyDrawX = timeToX(maxDep);
                                    if (minArr !== Infinity) familyFallbackX = timeToX(minArr);

                                } else {
                                    // 🚄 【分離模式 SPLIT】
                                    let sharedArr = minArr !== Infinity ? minArr : null;
                                    let splits = [
                                        { t: iA.dep, str: `${formatTimeDisplay(iA.dep)}(${iA.dest})` },
                                        { t: iB.dep, str: `${formatTimeDisplay(iB.dep)}(${iB.dest})` }
                                    ].sort((a,b) => (a.t || 0) - (b.t || 0));
                                    
                                    displayText = `${formatTimeDisplay(sharedArr)}-${splits[0].str}/${splits[1].str} ${stationName}`;
                                    
                                    // 🌟 更新外圍已經宣告好的變數 (直接覆寫值，不要加 let！)
                                    familyAlign = 'left'; 
                                    if (maxDep !== -Infinity) familyDrawX = timeToX(maxDep);
                                    if (minArr !== Infinity) familyFallbackX = timeToX(minArr);
                                }
                            } else {
                                // 聚合時刻：取 myFamily 所有成員在此站最早到達、最晚出發
                                // 只合併時間接近（≤10分）的成員，避免把不同批次的天王寺停靠混在一起
                                let clusterArr = arrT;
                                let clusterDep = depT;
                                const refTime = (typeof arrT === 'number' ? arrT : depT) ?? 0;
                                const _stId = String(seg.s[i]);
                                const _trainId = String(train.no || train.train_no || train.id);
                                for (let ft of myFamily) {
                                    if (ft === train || !ft.segments) continue;
                                    const _ftId = String(ft.no || ft.train_no || ft.id);
                                    // 直通串聯的成員不受 10 分鐘門檻限制（如 4631H→395M 在和歌山銜接）
                                    let isDirectChainHere = (
                                        (train.coupled_with && train.coupled_with.some(c =>
                                            c.action === "direct" && String(c.station_id) === _stId && String(c.train_id) === _ftId)) ||
                                        (ft.coupled_with && ft.coupled_with.some(c =>
                                            c.action === "direct" && String(c.station_id) === _stId && String(c.train_id) === _trainId))
                                    );
                                    for (let fSeg of ft.segments) {
                                        let fi = fSeg.s.findIndex(s => String(s) === _stId);
                                        if (fi < 0) continue;
                                        let fArr = fSeg.t[fi * 2];
                                        let fDep = fSeg.t[fi * 2 + 1];
                                        // 時間接近才納入聚合（拒絕同站不同批次），但直通串聯不受此限
                                        let fRef = typeof fArr === 'number' ? fArr : (typeof fDep === 'number' ? fDep : null);
                                        if (fRef === null || (!isDirectChainHere && Math.abs(fRef - refTime) > 10)) break;
                                        if (typeof fArr === 'number' && (clusterArr === null || fArr < clusterArr)) clusterArr = fArr;
                                        if (typeof fDep === 'number' && (clusterDep === null || fDep > clusterDep)) clusterDep = fDep;
                                        break;
                                    }
                                }
                                let cArr = formatTimeDisplay(clusterArr);
                                let cDep = formatTimeDisplay(clusterDep);
                                if (cArr === cDep) displayText = `${cArr} ${stationName}`;
                                else displayText = `${cArr}-${cDep} ${stationName}`;
                            }
                        } else {
                            displayText = ""; 
                        }

                        // ==========================================
                        // 🌟 4. 全域記憶體防護網 
                        // ==========================================
                        if (displayText !== "") {
                            // copy 編號納入 key：環狀圖每個複製版各自獨立，不互相抑制
                            // 原始時間納入 key：跨夜殘影與今日車在同站同名但時間相差 1440（不同 x 位置不重疊），需各自印出
                            let _tKey = (seg.t[i * 2] !== "" && seg.t[i * 2] != null) ? seg.t[i * 2] : seg.t[i * 2 + 1];
                            let uniqueKey = `${copy}_${seg.s[i]}_${_tKey}_${displayText}`;
                            if (printedStationTexts.has(uniqueKey)) {
                                displayText = ""; 
                            } else {
                                printedStationTexts.add(uniqueKey);
                            }
                        }
                        // --- 5. 畫出文字 (雙向智慧防撞牆版) ---
                        if (displayText !== "") {
                            ctx.font = '14px "GlowSans", "Segoe UI", sans-serif'; 
                            ctx.fillStyle = isDarkMode ? '#FFFFFF' : '#000000'; 
                            ctx.textBaseline = 'middle';
                            ctx.shadowColor = isDarkMode ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.8)';
                            ctx.shadowBlur = 4;

                            let textWidth = ctx.measureText(displayText).width;

                            if (familyAlign === 'right') {
                                if (familyDrawX - 8 - textWidth < leftBoundary) {
                                    ctx.textAlign = 'left';
                                    ctx.fillText(displayText, familyFallbackX + 8, y); 
                                } else {
                                    ctx.textAlign = 'right';
                                    ctx.fillText(displayText, familyDrawX - 8, y);
                                }
                            } else {
                                if (familyDrawX + 8 + textWidth > rightBoundary) {
                                    ctx.textAlign = 'right';
                                    ctx.fillText(displayText, familyFallbackX - 8, y); 
                                } else {
                                    ctx.textAlign = 'left';
                                    ctx.fillText(displayText, familyDrawX + 8, y);
                                }
                            }
                        }
                    }

                    ctx.restore(); 
                }
            }
        });
    };
    // ==========================================
    // 結束打包
    // ==========================================


    // 🌟 真正的繪圖流程開始！(分四層畫)
    let vipTrain = null;
    let hoverTrainDraw = null;
    let partnerTrains = []; 

    // ==========================================
    // 🌟 效能大躍進：改用「快取機制」代替每幀重算！
    // 只有在「選中的火車/車站發生改變」時，才重新執行 BFS，否則直接讀取快取。
    // ==========================================
    
    // 判斷列車是否為環狀的輔助函式
    const _isCircularTrain = (t) => {
        if (!t.segments || t.segments.length === 0) return false;
        const fSt = String(t.segments[0].s[0]);
        const lSeg = t.segments[t.segments.length - 1];
        return fSt === String(lSeg.s[lSeg.s.length - 1]);
    };

    // 每次畫圖前，只要讀取剛剛存好的快取結果就好
    let partnerIds = selectedTrain ? cachedPartnerIds : new Set();
    let selectedNoStr = selectedTrain ? String(selectedTrain.no || selectedTrain.train_no || selectedTrain.id) : null;
    let stationChainSet = null;
    if (selectedStation && timetable) {
        if (!cachedStationChainSet || cachedStationChainSet._forStation !== selectedStation) {
            const s = new Set();
            s._forStation = selectedStation;
            for (const t of timetable) {
                const no = String(t.no || t.train_no || t.id);
                let hit = false;
                for (const seg of t.segments || []) {
                    if (hit) break;
                    for (let i = 0; i < seg.s.length; i++) {
                        if (String(seg.s[i]) === String(selectedStation) && seg.v[i] !== 2) {
                            s.add(no); hit = true; break;
                        }
                    }
                }
            }
            cachedStationChainSet = s;
        }
        stationChainSet = cachedStationChainSet;
    }

    // 每幀重置站名去重 Set，讓 VIP/Partner 的 drawSingleTrain 共享同一組記憶
    const printedStationTexts = new Set();

    // 第一次迴圈：畫普通車，把 VIP、Hover 和 Partner 扣留起來
    timetable.forEach(train => {
    // ... (下面接續你原本的 timetable.forEach 邏輯)
        
        if (!train._hitPoints) train._hitPoints = [];
        train._hitPoints.length = 0; 

        let trainNoStr = String(train.no || train.train_no || train.id || "");
        if (activeRouteFilterTrains !== null && !activeRouteFilterTrains.has(trainNoStr)) {
            return; 
        }

        if (!activeTrainTypes.has(train.type)) return; 
        
        // ==========================================
        // 🌟 找回遺失的車站過濾邏輯 (Focus Mode)
        // ==========================================
        if (stationChainSet && !stationChainSet.has(trainNoStr)) return;

        // 🌟 3. 狀態判斷與分發 (加入伴侶車攔截)
        if (train === selectedTrain) {
            vipTrain = train;
        } else if (selectedNoStr && trainNoStr === selectedNoStr) {
            // 跨夜殘影：與選取車同車號的另一份拷貝，一樣高亮（與選取家族其他成員時的行為一致）
            partnerTrains.push(train);
        } else if (partnerIds.has(trainNoStr)) {
            partnerTrains.push(train); // 攔截伴侶車！
        } else if (train === hoveredTrain) {
            hoverTrainDraw = train;
        } else {
            drawSingleTrain(train, false, false, false); 
        }
    });

    // 依序畫上層 (越後面畫的會壓在越上面)
    
    // 第二次：畫懸停的車
    if (hoverTrainDraw) drawSingleTrain(hoverTrainDraw, false, true, false); 
    
    // 🌟 第三次：畫伴侶車 (壓在普通車與懸停車的上方)
    partnerTrains.forEach(pTrain => drawSingleTrain(pTrain, false, false, true));

    // 第四次：畫點擊的主角 VIP 車 (永遠壓在最上面，也就是那條黃線)
    if (vipTrain) drawSingleTrain(vipTrain, true, false, false); 

    ctx.restore();
}

// ==========================================
// 🕒 繪製現在時間線 (跨夜影分身 + 智慧邊界版)
// ==========================================
function drawCurrentTimeLine() {
    const now = new Date();
    let currentMinutes = getCurrentSystemMinutes();

    // 🌟 抓取真實的螢幕高度，而不是被高畫質放大的 canvas.height
    const wrapper = document.getElementById('canvas-wrapper');
    const wrapperH = wrapper ? wrapper.clientHeight : canvas.height;
    const wrapperW = wrapper ? wrapper.clientWidth : canvas.width;

    const viewTop = camera.y;
    const viewBottom = camera.y + wrapperH; // 邊界對齊螢幕底部
    const viewLeft = camera.x;
    const viewRight = camera.x + wrapperW;

    // 🌟 拔除 _view 錯字！讓系統正確辨識環狀線，不再強制截斷紅線！
    let presetKey = currentRouteView; 
    let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
    let routeStartY = CONFIG.paddingTop;
    let routeEndY = CONFIG.paddingTop + loopHeight;

    let lineTop = isCircular ? viewTop : Math.max(viewTop, routeStartY - 20);
    let lineBottom = isCircular ? viewBottom : Math.min(viewBottom, routeEndY + 20);

    ctx.save();
    ctx.translate(-camera.x, -camera.y);

    ctx.strokeStyle = "rgba(255, 80, 80, 0.9)";
    ctx.lineWidth = 2.0;
    ctx.setLineDash([6, 4]);
    ctx.fillStyle = "rgba(255, 80, 80, 0.9)";
    ctx.font = "bold 14px 'GlowSans', sans-serif";
    ctx.textAlign = "left";

    // 🌟 修正：只有當現在時間是凌晨 00:00 ~ 01:59 (即小於 120 分鐘) 時，才畫跨夜的影分身
    let timeCopies = [currentMinutes];
    if (currentMinutes < 120) {
        timeCopies.push(currentMinutes + 1440);
    }

    timeCopies.forEach(mins => {
        let x = timeToX(mins);

        if (x >= viewLeft && x <= viewRight) {
            ctx.beginPath();
            ctx.moveTo(x, lineTop);
            ctx.lineTo(x, lineBottom);
            ctx.stroke();

            // 讓紅線標籤也跟著智慧浮動，且保證不超出螢幕底部
            let labelY = isCircular 
                ? Math.max(viewTop + 60, CONFIG.paddingTop) 
                : Math.max(lineTop + 40, Math.min(viewBottom - 30, lineBottom - 20));
            
            let displayH = Math.floor(currentMinutes / 60);
            let displayM = currentMinutes % 60;
            ctx.fillText(displayH + ":" + displayM.toString().padStart(2, '0'), x + 8, labelY);
        }
    });

    ctx.restore();
}

// ==========================================
// 5. UI 構建與事件綁定 (完美底色版)
// ==========================================

// ==========================================
// 🌟 終極防跳動換線處理 (中央對焦雙軸記憶 + 智慧路線整理)
// ==========================================
function handleRouteSwitch(newRoute) {
    if (currentRouteView === newRoute) return;

    // 取得畫布容器的真實尺寸，用來計算「螢幕正中央」
    const wrapper = document.getElementById('canvas-wrapper');
    const screenW = wrapper ? wrapper.clientWidth : canvas.width;
    const screenH = wrapper ? wrapper.clientHeight : canvas.height;

    // --- 1. 雙軸記憶：精準記下螢幕「正中央」的時間 (X) 和里程 (Y) ---
    let anchorDataX = 0;
    let anchorDataY = 0;
    if (loopKm > 0) {
        // 算出螢幕正中央的 X 座標
        let centerCamX = camera.x + (screenW / 2);
        anchorDataX = (centerCamX - CONFIG.paddingLeft) / CONFIG.scaleX; 
        
        // 算出螢幕正中央的 Y 座標 (加上降維運算)
        let centerCamY = camera.y + (screenH / 2);
        const currentLoopHeight = loopKm * CONFIG.scaleY;
        let relativeY = (centerCamY - CONFIG.paddingTop) % currentLoopHeight;
        if (relativeY < 0) relativeY += currentLoopHeight;
        anchorDataY = relativeY / CONFIG.scaleY; 
    }

    // --- 2. 切換狀態與 UI ---
    currentRouteView = newRoute;
    if (window.updateRouteButtons) window.updateRouteButtons();

    // --- 3. 背景偷偷計算新路線的總長度 (智慧整理器) ---
    let newLoopKm = 0;
    let selectedSegments = settings?.view_presets?.[newRoute]?.lines || [];
    let segmentsData = getProcessedSegments(selectedSegments, topology);
    
    segmentsData.forEach(data => {
        let stationsToDraw = data.stations;
        if (stationsToDraw.length > 0) {
            let startKm = stationsToDraw[0].km;
            let endKm = stationsToDraw[stationsToDraw.length - 1].km;
            newLoopKm += Math.abs(endKm - startKm);
        }
    });
    
    loopKm = newLoopKm;
    

    autoFitScale();

    // --- 5. 座標補償：以「螢幕正中央」為基準，還原時間和里程 ---
    // 先算出目標時間和里程在新比例下的「絕對像素座標」
    let targetCenterX = CONFIG.paddingLeft + (anchorDataX * CONFIG.scaleX);
    let targetCenterY = CONFIG.paddingTop + (anchorDataY * CONFIG.scaleY);

    // 把鏡頭的左上角 (camera.x, camera.y) 減去螢幕一半，精準推回中央！
    camera.x = Math.round(targetCenterX - (screenW / 2));
    camera.y = Math.round(targetCenterY - (screenH / 2));

    // --- 6. 防禦性校正 (撞牆保護) ---
    if (loopKm > 0) loopHeight = loopKm * CONFIG.scaleY;
    checkInfiniteScroll();
    clampCamera();

    // --- 7. 安全重繪最終畫面 ---
    redrawAll();

    updateTrainTypeVisibility();
}

// 取得車種顏色陣列，相容舊格式（平鋪）和新格式（巢狀分組）
function getTrainColorValue(type) {
    if (!settings?.train_color) return null;
    const tc = settings.train_color;
    if (settings._trainColorGrouped) {
        for (const group of Object.values(tc)) {
            if (group[type]) return group[type];
        }
        return null;
    }
    return tc[type] || null;
}

function buildUI() {
    // ---- 取得當下主題色碼的輔助函數 ----
    function getColor(colorsArray) {
        if (!colorsArray) return isDarkMode ? "#555" : "#CCC";
        return isDarkMode ? colorsArray[0] : colorsArray[1];
    }

    // ---- A. 🌟 動態產生路線切換按鈕 (支援超過10條自動轉為下拉選單) ----
    const routeContainer = document.getElementById('route-type-container');
    if (routeContainer) routeContainer.innerHTML = ''; 

    // 抓出 setting.json 裡面所有的視角 key
    const viewKeys = Object.keys(settings?.view_presets || {});

    // 如果視角只有 1 個(或沒有)，直接把整個切換區塊隱藏
    if (viewKeys.length <= 1) {
        if (routeContainer) routeContainer.style.display = 'none';
        let routeTitle = document.getElementById('route-title');
        if (routeTitle) routeTitle.style.display = 'none';
    } else {
        if (routeContainer) routeContainer.style.display = ''; 
        let routeTitle = document.getElementById('route-title');
        if (routeTitle) routeTitle.style.display = '';
    }
    
    // 核心防呆：如果目前記憶的視角「不在」新系統的視角清單中，強制洗掉重置
    if (viewKeys.length > 0 && !viewKeys.includes(currentRouteView)) {
        currentRouteView = viewKeys[0];
    }

    const dynamicRouteBtns = [];
    let routeSelectBox = null; // 🌟 紀錄下拉選單物件

    const updateRouteButtons = () => {
        let defaultBg = isDarkMode ? "#444444" : "#E0E0E0";
        let defaultBorder = isDarkMode ? "#555555" : "#CCCCCC";
        let defaultText = isDarkMode ? "#CCCCCC" : "#000000";
        let selectedText = isDarkMode ? "#000000" : "#FFFFFF";

        // 更新按鈕樣式 (如果當前是按鈕模式)
        dynamicRouteBtns.forEach(item => {
            let btn = item.btn;
            if (currentRouteView === item.key) {
                let routeColor = getColor(settings.view_presets[item.key].button_color);
                btn.style.backgroundColor = routeColor;
                btn.style.borderColor = routeColor;
                btn.style.color = selectedText;
            } else {
                btn.style.backgroundColor = defaultBg;
                btn.style.borderColor = defaultBorder;
                btn.style.color = defaultText;
            }
        });

        // 🌟 更新下拉選單的選中狀態與邊框顏色 (如果當前是選單模式)
        if (routeSelectBox) {
            routeSelectBox.value = currentRouteView;
            let routeColor = getColor(settings?.view_presets?.[currentRouteView]?.button_color);
            // 如果該路線有特殊設定顏色，就讓選單外框發光，否則套用預設邊框
            routeSelectBox.style.borderColor = routeColor !== (isDarkMode ? "#555" : "#CCC") ? routeColor : defaultBorder;
        }
    };

    // ==========================================
    // 🌟 核心判斷：超過 1 條用下拉選單，否則用按鈕
    // ==========================================
    if (viewKeys.length > 1) {
        if (routeContainer) routeContainer.className = 'select-group'; // 拔掉 flex 避免排版跑位
        
        routeSelectBox = document.createElement('select');
        routeSelectBox.className = 'route-select'; // 掛上專屬 CSS
        
        viewKeys.forEach(key => {
            const preset = settings.view_presets[key];
            const option = document.createElement('option');
            option.value = key;
            option.textContent = preset.name;
            routeSelectBox.appendChild(option);
        });

        // 當下拉選單改變時，觸發跳轉
        routeSelectBox.addEventListener('change', (e) => {
            handleRouteSwitch(e.target.value);
        });

        if (routeContainer) routeContainer.appendChild(routeSelectBox);

    } else {
        if (routeContainer) routeContainer.className = 'btn-group'; // 恢復按鈕排版
        
        viewKeys.forEach(key => {
            const preset = settings.view_presets[key];
            const btn = document.createElement('button');
            btn.className = 'pill-btn';
            btn.textContent = preset.name; 
            
            btn.addEventListener('click', () => handleRouteSwitch(key));
            
            if (routeContainer) routeContainer.appendChild(btn);
            dynamicRouteBtns.push({ key: key, btn: btn });
        });
    }

    window.updateRouteButtons = updateRouteButtons; 
    updateRouteButtons();
    // ---- 路線切換區塊結束 ----

    // ---- B. 動態生成車種篩選按鈕 (通用萬用版，免寫 train_order) ----

    // 1. 抓出時刻表內實際有出現的車種集合
    // 注意：這裡刻意用全時刻表（不依 lookupY 過濾），確保切換路線視角時
    // 各視角專屬車種（如山陰只跑的まつかぜ）的 chip 一定存在於 DOM 中。
    // 顯示/隱藏邏輯由 updateTrainTypeVisibility() 負責。
    const dataTypes = new Set(timetable.map(t => t.type));
    
    let sortedTypes = [];
    
    // 2. 依照我們剛剛從純文字挖出來的 _rawOrder 來排序
    if (settings && settings._rawOrder && settings._rawOrder.length > 0) {
        settings._rawOrder.forEach(type => {
            if (dataTypes.has(type)) {
                sortedTypes.push(type);
            }
        });
    } else if (settings && settings.train_color) {
        // 保底機制：萬一正則表達式沒抓到，退回預設的 Object.keys
        Object.keys(settings.train_color).forEach(type => {
            if (dataTypes.has(type)) sortedTypes.push(type);
        });
    }

    // 3. 把資料有出現，但 setting.json 沒設定到的額外車種補在最後面
    dataTypes.forEach(type => {
        if (!sortedTypes.includes(type)) {
            sortedTypes.push(type);
        }
    });

    trainTypeContainer.innerHTML = '';
    
    // ==========================================
    // 🌟 新增：連動更新底部面板的專屬函數
    // ==========================================
    const syncBottomPanel = () => {
        if (selectedStation) {
            // 如果正在看車站面板，直接重新整理
            updateBottomPanelStation(selectedStation);
        } else if (selectedTrain) {
            // 如果正在看火車面板，但該車種被取消勾選了，就清空面板
            if (!activeTrainTypes.has(selectedTrain.type)) {
                selectedTrain = null;
                updateBottomPanel(null);
            }
        }
    };

    // 4. 建立個別車種按鈕的工廠函數（共用邏輯）
    const makeTypeBtn = (type) => {
        activeTrainTypes.add(type);
        const btn = document.createElement('button');
        btn.className = 'pill-btn';
        btn.textContent = type;
        const updateStyle = () => {
            let defaultBg = isDarkMode ? "#444444" : "#E0E0E0";
            let defaultBorder = isDarkMode ? "#555555" : "#CCCCCC";
            let defaultText = isDarkMode ? "#CCCCCC" : "#000000";
            let selectedText = isDarkMode ? "#000000" : "#FFFFFF";
            if (activeTrainTypes.has(type)) {
                let tColor = getColor(getTrainColorValue(type));
                btn.style.backgroundColor = tColor;
                btn.style.borderColor = tColor;
                btn.style.color = selectedText;
            } else {
                btn.style.backgroundColor = defaultBg;
                btn.style.borderColor = defaultBorder;
                btn.style.color = defaultText;
            }
        };
        updateStyle();
        btn._updateStyle = updateStyle;
        btn.addEventListener('click', () => {
            if (activeTrainTypes.has(type)) activeTrainTypes.delete(type);
            else activeTrainTypes.add(type);
            updateStyle();
            syncBottomPanel();
            redrawAll();
        });
        return btn;
    };

    // 5. 分組格式 vs 平鋪格式的渲染
    window._allGroupUpdateFns = []; // 提升到 window，主題切換時也能呼叫
    const allGroupUpdateFns = window._allGroupUpdateFns;
    if (settings._trainColorGrouped && settings.train_color) {
        // 巢狀分組：群組標題可折疊，點標題可全選/全取消該群組
        const groupBorderColor = isDarkMode ? "#444" : "#ddd";
        Object.entries(settings.train_color).forEach(([groupLabel, groupTypes]) => {
            const groupTypesInData = Object.keys(groupTypes).filter(t => sortedTypes.includes(t));
            if (groupTypesInData.length === 0) return;

            // 群組容器
            const groupDiv = document.createElement('div');
            groupDiv.className = 'train-type-group';
            groupDiv.style.cssText = `width:100%; margin-bottom:4px; border:1px solid ${groupBorderColor}; border-radius:8px; overflow:hidden;`;

            // 群組標題列
            const header = document.createElement('div');
            header.style.cssText = `display:flex; align-items:center; gap:6px; padding:4px 10px; cursor:pointer; user-select:none; font-size:12px; font-weight:bold; color:${isDarkMode?"#aaa":"#555"};`;
            const arrow = document.createElement('span');
            arrow.textContent = '▶';
            arrow.style.cssText = 'font-size:9px; transition:transform 0.2s;';
            const label = document.createElement('span');
            label.textContent = groupLabel;
            label.style.flex = '1';

            // 群組全選/全取消按鈕
            const groupToggleBtn = document.createElement('button');
            groupToggleBtn.style.cssText = `font-size:10px; padding:1px 6px; border-radius:4px; border:1px solid; cursor:pointer; font-weight:normal;`;
            const updateGroupToggle = () => {
                const allOn  = groupTypesInData.every(t => activeTrainTypes.has(t));
                const anyOn  = groupTypesInData.some(t => activeTrainTypes.has(t));
                const bg  = isDarkMode ? "#444" : "#e8e8e8";
                const bdr = isDarkMode ? "#666" : "#ccc";
                groupToggleBtn.textContent = allOn ? '全部不選' : '全選';
                groupToggleBtn.style.backgroundColor = allOn ? (isDarkMode?"#555":"#ddd") : bg;
                groupToggleBtn.style.borderColor = bdr;
                groupToggleBtn.style.color = isDarkMode ? "#ccc" : "#444";
                groupToggleBtn.style.opacity = anyOn || !allOn ? '1' : '0.6';
            };
            groupToggleBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const allOn = groupTypesInData.every(t => activeTrainTypes.has(t));
                if (allOn) groupTypesInData.forEach(t => activeTrainTypes.delete(t));
                else       groupTypesInData.forEach(t => activeTrainTypes.add(t));
                // 更新群組內個別按鈕樣式
                content.querySelectorAll('.pill-btn').forEach(b => { if (b._updateStyle) b._updateStyle(); });
                updateGroupToggle();
                syncBottomPanel();
                redrawAll();
            });
            updateGroupToggle();
            allGroupUpdateFns.push(updateGroupToggle);
            header.append(arrow, label, groupToggleBtn);

            // 群組內容（預設折疊）
            const content = document.createElement('div');
            content.style.cssText = `display:none; flex-wrap:wrap; gap:6px; padding:6px 8px;`;

            // 展開/折疊切換
            header.addEventListener('click', (e) => {
                if (e.target.closest('button')) return;
                const open = content.style.display === 'none';
                content.style.display = open ? 'flex' : 'none';
                arrow.style.transform = open ? 'rotate(90deg)' : '';
            });

            // 加入各車種按鈕（點個別按鈕後同步更新群組狀態）
            groupTypesInData.forEach(type => {
                const btn = makeTypeBtn(type);
                btn.addEventListener('click', () => updateGroupToggle());
                content.appendChild(btn);
            });
            groupDiv.append(header, content);
            trainTypeContainer.appendChild(groupDiv);
        });
        // 不在任何分組的車種補在最後（平鋪）
        const grouped = new Set(Object.values(settings.train_color).flatMap(g => Object.keys(g)));
        sortedTypes.filter(t => !grouped.has(t)).forEach(type => trainTypeContainer.appendChild(makeTypeBtn(type)));
    } else {
        // 舊格式：平鋪
        sortedTypes.forEach(type => trainTypeContainer.appendChild(makeTypeBtn(type)));
    }

    // ==========================================
    // 🌟 修正：將 addEventListener 改成 onclick
    // ==========================================
    // 全選
    btnAllTrains.onclick = () => {
        activeTrainTypes = new Set(sortedTypes);
        document.querySelectorAll('#train-type-container .pill-btn').forEach(b => { if(b._updateStyle) b._updateStyle(); });
        allGroupUpdateFns.forEach(fn => fn());
        syncBottomPanel();
        redrawAll();
    };

    // 全部不選
    btnNoTrains.onclick = () => {
        activeTrainTypes.clear();
        document.querySelectorAll('#train-type-container .pill-btn').forEach(b => { if(b._updateStyle) b._updateStyle(); });
        allGroupUpdateFns.forEach(fn => fn());
        syncBottomPanel();
        redrawAll();
    };
    
    // ==========================================
    // 🌟 側邊欄收合功能綁定 (修復幽靈連點 Bug)
    // ==========================================
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('sidebar-toggle');

    if (sidebar && toggleBtn) {
        // 🌟 核心修復：把 addEventListener 改成 onclick，保證這輩子永遠只有一個點擊事件！
        toggleBtn.onclick = () => {
            sidebar.classList.toggle('collapsed');
            
            // 切換箭頭方向
            toggleBtn.textContent = sidebar.classList.contains('collapsed') ? '‹' : '›';

            // 等待動畫跑完 (0.3秒)，重新測量並放大畫布
            setTimeout(() => {
                const wrapper = document.getElementById('canvas-wrapper');
                if (wrapper) {
                    // 🌟 這裡也確保換上我們的高畫質工具，防止側欄收合時畫質變糊！
                    initCanvas('diaCanvas', 'canvas-wrapper');
                    clampCamera();
                    redrawAll();
                }
            }, 300); 
        };
    }
}

// ==========================================
// 🌟 搜尋框文字同步助手
// ==========================================
window.updateSearchInputText = function(text) {
    const searchInput = document.getElementById('search-input');
    const clearBtn = document.getElementById('search-clear-btn');
    if (searchInput) {
        searchInput.value = text;
        // 同步顯示或隱藏右側的叉叉按鈕
        if (clearBtn) clearBtn.style.display = text.length > 0 ? 'block' : 'none';
    }
};

// ==========================================
// 🌟 歷史紀錄管理器 (LocalStorage)
// ==========================================
window.SearchHistoryManager = {
    key: 'tra_search_history',
    maxItems: 5, // 最多記憶 5 筆
    get() {
        try { return JSON.parse(localStorage.getItem(this.key)) || []; }
        catch (e) { return []; }
    },
    add(item) {
        let history = this.get();
        // 🌟 核心修正：改用 ID 判斷重複，避免日本私鐵多班「区間急行」互相覆蓋
        history = history.filter(h => (h.id ? h.id !== item.id : h.keyword !== item.keyword));
        history.unshift(item);
        if (history.length > this.maxItems) history.pop();
        localStorage.setItem(this.key, JSON.stringify(history));
    },
    clear() {
        localStorage.removeItem(this.key);
    },
    render() {
        let history = this.get();
        const searchResults = document.getElementById('search-results');
        if (!searchResults) return;

        if (history.length === 0) {
            searchResults.style.display = 'none';
            return;
        }

        let textColor = isDarkMode ? "#BBBBBB" : "#666666";
        let borderColor = isDarkMode ? "#444444" : "#DDDDDD";
        let clearColor = isDarkMode ? "#FF6666" : "#FF3333";

        let html = `<div style="padding: 8px 12px; font-size: 13px; color: ${textColor}; border-bottom: 1px solid ${borderColor}; display: flex; justify-content: space-between; align-items: center;">
                        <span>🕒 最近搜尋</span>
                        <span style="cursor: pointer; color: ${clearColor}; font-weight: bold;" onclick="clearSearchHistory(event)">清除</span>
                    </div>`;
        
        html += history.map((item, index) => {
            return `<div class="search-item selectable-item" style="display: flex; align-items: center;" onclick="triggerHistorySelect(${index})">
                        ${item.displayHtml}
                    </div>`;
        }).join('');
        
        searchResults.innerHTML = html;
        searchResults.style.display = 'block';
    }
};

// ==========================================
// 🌟 專屬火車歷史紀錄產生器 (支援隱藏設定與起訖時間)
// ==========================================
window.buildTrainHistoryData = function(train) {
    if (!train) return { id: "", keyword: "未知", displayHtml: "未知" };
    
    let rawNo = train.no || train.train_no || train.id || "未知";
    let trainNo = String(rawNo).split('|')[0];
    let tType = train.type || "";
    
    // 1. 讀取顯示設定
    let showType = !(settings && settings.show_train_type === false);
    let showId = !(settings && settings.show_train_id === false);
    
    let displayTitle = "";
    if (showType && showId) displayTitle = `${tType} ${trainNo}`;
    else if (showType && !showId) displayTitle = `${tType}`; // 如：区間急行
    else if (!showType && showId) displayTitle = `${trainNo}`; // 如：高鐵 0111
    else displayTitle = "列車";

    // 2. 抓取起終點與時間
    let startStationName = "未知";
    let endStationName = "未知";
    let startTime = "--:--";
    let endTime = "--:--";

    if (train.segments && train.segments.length > 0) {
        let firstSeg = train.segments[0];
        let lastSeg = train.segments[train.segments.length - 1];
        
        startStationName = getStationName(firstSeg.s[0]);
        endStationName = getStationName(lastSeg.s[lastSeg.s.length - 1]);
        
        let tStartRaw = firstSeg.t[0] !== null ? firstSeg.t[0] : firstSeg.t[1];
        let tEndRaw = lastSeg.t[lastSeg.t.length - 1] !== null ? lastSeg.t[lastSeg.t.length - 1] : lastSeg.t[lastSeg.t.length - 2];
        
        if (typeof formatTimeDisplay === 'function') {
            startTime = formatTimeDisplay(tStartRaw);
            endTime = formatTimeDisplay(tEndRaw);
        }
    }

    // 3. 組裝精美 UI
    let displayHtml = `
        <div style="display: flex; align-items: center; width: 100%;">
            <span class="search-item-badge badge-train">車次</span> 
            <span style="margin-left: 8px; margin-right: 8px; font-weight: bold;">${displayTitle}</span> 
            <span style="font-size: 13px; opacity: 0.8; margin-left: auto; display: flex; align-items: center; gap: 6px;">
                <span>${startStationName}</span>
                <span style="font-family: monospace;">${startTime}</span>
                <span style="color: #888;">➔</span>
                <span>${endStationName}</span>
                <span style="font-family: monospace;">${endTime}</span>
            </span>
        </div>`;
        
    return { id: trainNo, keyword: displayTitle, displayHtml: displayHtml };
};
// ==========================================

// 綁定給 HTML 呼叫的清除全域函數
window.clearSearchHistory = function(e) {
    e.stopPropagation();
    SearchHistoryManager.clear();
    document.getElementById('search-results').style.display = 'none';
};

// 綁定給 HTML 呼叫的歷史紀錄點擊函數
window.triggerHistorySelect = function(index) {
    let history = SearchHistoryManager.get();
    let item = history[index];
    if (!item) return;

    window.updateSearchInputText(item.keyword);
    
    if (item.type === 'station' || item.type === 'train') {
         // false 代表不要重複再存一次歷史紀錄
         window.triggerSearchSelect(item.type, item.id, null, false);
    } else if (item.type === 'route') {
         // 如果是區間車次，觸發 input 事件重新計算路線過濾
         const searchInput = document.getElementById('search-input');
         searchInput.dispatchEvent(new Event('input'));
         document.getElementById('search-results').style.display = 'none';
    }
};

// ==========================================
// 🌟 全域變數：用來記錄「路線過濾」模式下，目前符合的車次號碼
// ==========================================
let activeRouteFilterTrains = null; // null 代表沒有啟用路線過濾，Set() 代表有啟用

// ==========================================
// 🌟 搜尋功能整合 (修復跨系統閉包陷阱版)
// ==========================================
let isSearchBound = false;

function setupSearch() {
    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');
    const clearBtn = document.getElementById('search-clear-btn'); // 🌟 新增：抓取叉叉按鈕
    
    if (!searchInput || !searchResults) return;

    // 🌟 修正 1：移到綁定檢查之前
    // 確保每次切換系統時，提示文字都能正確更新
    let showId = !(settings && settings.show_train_id === false);
    // 範例路線：優先用 setting.search_example（環狀線等自動推導不出時可明確指定），
    // 否則從第一個 view preset 的起站~迄站自動取，再否則用拓樸首段首站~末段末站，
    // 避免寫死台鐵/私鐵站名套錯系統。
    let exampleRoute = (settings && settings.search_example) ? settings.search_example : "";
    if (!exampleRoute) {
        try {
            const segName = (id, which) => {
                let seg = topology.segments.find(s => s.id === id);
                if (!seg || !seg.stations.length) return null;
                return which === 'start' ? seg.stations[0].name : seg.stations[seg.stations.length - 1].name;
            };
            const endName = (lineEl, which) => {
                if (lineEl && typeof lineEl === 'object') {
                    if (which === 'start' && lineEl.start) return lineEl.start;
                    if (which === 'end' && lineEl.end) return lineEl.end;
                    return segName(lineEl.id, which);
                }
                return segName(lineEl, which);
            };
            let a = null, b = null;
            let preset = settings && settings.view_presets ? Object.values(settings.view_presets)[0] : null;
            let lines = preset && preset.lines ? preset.lines : null;
            if (lines && lines.length && topology && topology.segments) {
                a = endName(lines[0], 'start');
                b = endName(lines[lines.length - 1], 'end');
            }
            // preset 推不出（無 preset、或環狀首尾同站）→ 退用拓樸首段~末段
            if ((!a || !b || a === b) && topology && topology.segments && topology.segments.length) {
                a = segName(topology.segments[0].id, 'start');
                b = segName(topology.segments[topology.segments.length - 1].id, 'end');
            }
            if (a && b && a !== b) exampleRoute = `${a}~${b}`;
        } catch (e) {}
    }
    let exHint = exampleRoute ? ` (如: ${exampleRoute})` : "";
    searchInput.placeholder = (showId ? "車站、車次 或 路線找車" : "輸入車站 或 路線找車") + exHint;

    if (isSearchBound) return;
    isSearchBound = true;

    // ==========================================
    // 🌟 新增：綁定叉叉按鈕的點擊事件 (功能 100% 等同 ESC 鍵)
    // ==========================================
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            let needsRedraw = false;

            // 1. 清空火車與車站的選取狀態，並重置底部面板
            if (selectedTrain || selectedStation) {
                selectedTrain = null;
                selectedStation = null;
                if (typeof updateBottomPanel === 'function') updateBottomPanel(null);
                needsRedraw = true;
            }

            // 2. 清空搜尋框、隱藏下拉選單、隱藏叉叉自己
            searchInput.value = '';
            searchResults.style.display = 'none';
            clearBtn.style.display = 'none'; 

            // 3. 解除路線過濾模式
            if (activeRouteFilterTrains !== null) {
                activeRouteFilterTrains = null;
                needsRedraw = true;
            }

            // 4. 重繪乾淨的畫布
            if (needsRedraw) {
                if (typeof requestRedraw === 'function') requestRedraw();
                else if (typeof redrawAll === 'function') redrawAll();
            }
        });
    }

    let currentFocus = -1; 

    document.addEventListener('click', (e) => {
        const themeBtn = document.getElementById('btn-theme');
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)
            && !(themeBtn && themeBtn.contains(e.target))) {
            searchResults.style.display = 'none';
        }
    });

    // 🌟 新增：點擊搜尋框時，如果是空的就顯示歷史紀錄
    searchInput.addEventListener('focus', () => {
        if (searchInput.value.trim().length === 0) {
            SearchHistoryManager.render();
        }
    });

    searchInput.addEventListener('input', (e) => {
        const rawText = e.target.value.trim().toLowerCase();

        // 🌟 新增：有打字就顯示叉叉，沒字就隱藏叉叉
        if (clearBtn) {
            clearBtn.style.display = rawText.length > 0 ? 'block' : 'none';
        }
        
        if (rawText.length === 0) {
            // 🌟 核心修改：如果是空的，不要隱藏，而是顯示歷史紀錄！
            SearchHistoryManager.render();
            if (activeRouteFilterTrains !== null) {
                activeRouteFilterTrains = null;
                if (typeof redrawAll === 'function') redrawAll(); 
            }
            return;
        }

        currentFocus = -1;
        const keywords = normalizeText(rawText).split(/[~\-\s,，、]+/).filter(k => k.length > 0);
        let searchData = [];
        let currentShowId = !(settings && settings.show_train_id === false);

        let previousFilterState = activeRouteFilterTrains;
        activeRouteFilterTrains = null; 

        // 🌟 修正 2：移至監聽器內部
        // 確保每次打字時，都是抓取當前系統最新的 topology (實體路線圖)
        let stationIdToNameMap = new Map();
        if (topology && topology.segments) {
            topology.segments.forEach(seg => {
                seg.stations.forEach(st => {
                    stationIdToNameMap.set(String(st.id), st.name);
                });
            });
        }

        // ==========================================
        // 模式 A：單關鍵字搜尋
        // ==========================================
        if (keywords.length === 1) {
            const keyword = keywords[0];
            let matchedStations = new Map(); 
            if (topology && topology.segments) {
                topology.segments.forEach(seg => {
                    seg.stations.forEach(st => {
                        let stName = st.name || "";
                        let stId = String(st.id || "");
                        let nameLower = normalizeText(stName);
                        let idLower = stId.toLowerCase();
                        let score = Math.max(
                            nameLower === keyword ? 3 : (nameLower.startsWith(keyword) ? 2 : (nameLower.includes(keyword) ? 1 : 0)),
                            idLower === keyword ? 3 : (idLower.startsWith(keyword) ? 2 : (idLower.includes(keyword) ? 1 : 0))
                        );
                        if (score > 0) {
                            if (!matchedStations.has(stName)) matchedStations.set(stName, { id: stId, name: stName, score: score });
                            else if (score > matchedStations.get(stName).score) matchedStations.get(stName).score = score; 
                        }
                    });
                });
            }
            matchedStations.forEach(data => searchData.push({ type: 'station', id: data.id, name: data.name, score: data.score }));

            if (currentShowId && timetable) {
                let matchedTrains = new Map(); 
                timetable.forEach(train => {
                    let trainNo = String(train.no || train.train_no || train.id || "");
                    let displayNo = trainNo.split('|')[0];
                    let displayNoLower = displayNo.toLowerCase();
                    let score = displayNoLower === keyword ? 3 : (displayNoLower.startsWith(keyword) ? 2 : (displayNoLower.includes(keyword) ? 1 : 0));
                    if (score > 0 && !matchedTrains.has(trainNo)) {
                        let startSta = "", endSta = "";
                        if (train.segments && train.segments.length > 0) {
                            let fSeg = train.segments[0];
                            let lSeg = train.segments[train.segments.length - 1];
                            if (fSeg.s && fSeg.s.length > 0) startSta = getStationName(String(fSeg.s[0]));
                            if (lSeg.s && lSeg.s.length > 0) endSta = getStationName(String(lSeg.s[lSeg.s.length - 1]));
                        }
                        matchedTrains.set(trainNo, { typeStr: train.type || "", no: trainNo, displayNo, score, startSta, endSta });
                    }
                });
                matchedTrains.forEach(data => searchData.push({ type: 'train', id: data.no, typeStr: data.typeStr, score: data.score, displayNo: data.displayNo, startSta: data.startSta, endSta: data.endSta }));
            }
        } 
        // ==========================================
        // 🌟 模式 B：多關鍵字路線搜尋 (BFS 跨車次拓樸尋路版)
        // 支援直通、拆解、併結的無縫搜尋！
        // ==========================================
        else if (keywords.length >= 2) {
            let startKeyword = keywords[0];
            let endKeyword = keywords[1];
            let filteredTrainNos = new Set(); 
            let uniqueSearchKeys = new Set();

            if (timetable) {
                // 1. 預先攤平所有車次的停靠站 (大幅提升 BFS 效能)
                let trainStopsCache = new Map();
                timetable.forEach(train => {
                    let stops = [];
                    if (train.segments) {
                        train.segments.forEach(seg => {
                            seg.s.forEach((stId, idx) => {
                                if (seg.v && seg.v[idx] === 2) return; // 跳過通過站
                                let nameStr = normalizeText(stationIdToNameMap.get(String(stId)) || "");
                                let idStr = String(stId).toLowerCase();

                                let isSingleTime = (seg.t.length === seg.s.length);
                                let arrTime = isSingleTime ? seg.t[idx] : seg.t[idx * 2];
                                let depTime = isSingleTime ? seg.t[idx] : seg.t[idx * 2 + 1];

                                let effDep = (depTime !== undefined && depTime !== null) ? depTime : arrTime;
                                let effArr = (arrTime !== undefined && arrTime !== null) ? arrTime : depTime;

                                stops.push({ stId: String(stId), nameStr, idStr, effArr, effDep });
                                
                                let tNo = String(train.no || train.train_no || train.id || "");
                            });
                        });
                    }
                    let cacheKey = String(train.no || train.train_no || train.id || "");
                    if (train._isYesterday) {
                        cacheKey += "_yest";
                    }
                    trainStopsCache.set(cacheKey, stops);
                });

                // 2. 開始全網掃描
                timetable.forEach(startTrain => {
                    let startTrainNo = String(startTrain.no || startTrain.train_no || startTrain.id || "");
    
                    // 🌟 讀取對應的專屬鑰匙
                    let cacheKey = startTrain._isYesterday ? startTrainNo + "_yest" : startTrainNo;
                    let stops = trainStopsCache.get(cacheKey);
                    
                    if (!stops) return;

                    // 找出這台車所有符合「起點」的車站
                    stops.forEach((startStop, sIdx) => {
                        if (startStop.idStr.includes(startKeyword) || startStop.nameStr.includes(startKeyword)) {
                            let startTime = startStop.effDep;

                            // 🌟 啟動 BFS 廣度優先搜尋，跨越車次尋找終點！
                            let queue = [{
                                tObj: startTrain,
                                tNo: startTrainNo,
                                stops: stops,
                                currIdx: sIdx, // 從匹配到的起點開始往後找
                                pathNos: [startTrainNo],
                                sTime: startTime
                            }];

                            // 防護網：防止循環路線導致無窮迴圈
                            let visited = new Set([startTrainNo]);

                            while (queue.length > 0) {
                                let curr = queue.shift();
                                let foundEnd = false;

                                // A. 先在「目前的車次」往下找終點
                                for (let i = curr.currIdx; i < curr.stops.length; i++) {
                                    let stop = curr.stops[i];

                                    
                                    if (stop.idStr.includes(endKeyword) || stop.nameStr.includes(endKeyword)) {
                                        let endTime = stop.effArr;
                                        
                                        // 確保時間是合理的 (沒有時光倒流，也沒有抓到昨天的殘影)
                                        if (endTime > curr.sTime && endTime >= 0) { 
                                            // 🎉 找到了！將這條路徑上的「所有車次」都加入高亮名單！
                                            curr.pathNos.forEach(n => filteredTrainNos.add(n));
                                            
                                            // 視覺指紋防重複
                                            let visualKey = `${startTrainNo}_${curr.sTime}_${endTime}`;
                                            if (!uniqueSearchKeys.has(visualKey)) {
                                                uniqueSearchKeys.add(visualKey);
                                                
                                                // 如果起迄車號不同，UI 顯示箭頭 (例如 159B ➔ 159M)
                                                let dispId = startTrainNo;
                                                if (startTrainNo !== curr.tNo) dispId = `${startTrainNo} ➔ ${curr.tNo}`;

                                                searchData.push({
                                                    type: 'train',
                                                    id: startTrainNo, 
                                                    dispId: dispId,   // 新增專門用來顯示的 ID
                                                    typeStr: startTrain.type || "",
                                                    startTime: curr.sTime,
                                                    endTime: endTime,
                                                    score: 3
                                                });
                                            }
                                        }
                                        foundEnd = true;
                                        break; 
                                    }
                                }

                                if (foundEnd) continue; // 這條分支已經找到目標，不需再往下擴散

                                // B. 如果這台車跑完了還沒找到，跟著 coupled_with 跨越到下一台車！
                                if (curr.tObj.coupled_with) {
                                    curr.tObj.coupled_with.forEach(c => {
                                        let nTrainNo = String(c.train_id);
                                        if (!visited.has(nTrainNo)) {
                                            let nTrain = timetable.find(t => String(t.no || t.train_no || t.id) === nTrainNo);
                                            let nStops = trainStopsCache.get(nTrainNo);
                                            
                                            if (nTrain && nStops) {
                                                // 物理驗證：確保拆解/併結的車站，是在我們上車的車站「之後」！
                                                let isValid = false;
                                                if (c.action === "direct") {
                                                    isValid = true; // 直通代表全車延續，無條件合法
                                                } else if (c.station_id) {
                                                    let actIdx = curr.stops.findIndex(st => st.stId === String(c.station_id));
                                                    if (actIdx >= curr.currIdx) isValid = true; 
                                                } else {
                                                    isValid = true;
                                                }

                                                if (isValid) {
                                                    visited.add(nTrainNo);
                                                    queue.push({
                                                        tObj: nTrain,
                                                        tNo: nTrainNo,
                                                        stops: nStops,
                                                        currIdx: 0, // 切換到新車，從第 0 站開始掃描
                                                        pathNos: [...curr.pathNos, nTrainNo],
                                                        sTime: curr.sTime
                                                    });
                                                }
                                            }
                                        }
                                    });
                                }
                            }
                        }
                    });
                });
            }
            // 路線搜尋完成後，把已篩出車次的 direct 前段/後段也一起加入
            // （如 関空快速 4156M 過京橋後直通的 普通，從京橋出發故不在原路徑內）
            if (filteredTrainNos.size > 0 && timetable) {
                let extraNos = new Set();
                timetable.forEach(t => {
                    let tNo = String(t.no || t.train_no || t.id || "");
                    if (!filteredTrainNos.has(tNo)) return;
                    // Forward: direct successor
                    if (t.coupled_with) {
                        t.coupled_with.forEach(c => {
                            if (c.action === "direct") extraNos.add(String(c.train_id));
                        });
                    }
                    // Backward: direct predecessor
                    if (t.segments && t.segments.length > 0) {
                        let tFirstSt = String(t.segments[0].s[0]);
                        timetable.forEach(pt => {
                            if (!pt.coupled_with || !pt.segments || pt.segments.length === 0) return;
                            let ptLast = pt.segments[pt.segments.length - 1];
                            if (String(ptLast.s[ptLast.s.length - 1]) !== tFirstSt) return;
                            if (pt.coupled_with.some(c => c.action === "direct" && String(c.train_id) === tNo)) {
                                extraNos.add(String(pt.no || pt.train_no || pt.id || ""));
                            }
                        });
                    }
                });
                extraNos.forEach(n => filteredTrainNos.add(n));
            }

            if (filteredTrainNos.size === 0 && timetable) {
                // 路線搜尋無結果 → fallback：嘗試「每個關鍵字符合車種 OR 車號」
                // 例如「普通 1552」→ keywords=["普通","1552"] → 找 type="普通" AND no includes "1552"
                let seenFallbackNos = new Set();
                timetable.forEach(train => {
                    let typeLower = (train.type || "").toLowerCase();
                    let fullId = String(train.no || train.train_no || train.id || "");
                    let noDisplay = fullId.split("|")[0];
                    let noLower = noDisplay.toLowerCase();
                    if (keywords.every(k => typeLower.includes(k) || noLower.includes(k))) {
                        if (!seenFallbackNos.has(noDisplay)) {
                            seenFallbackNos.add(noDisplay);
                            searchData.push({ type: 'train', id: fullId, typeStr: train.type || "", score: 2 });
                        }
                    }
                });
                activeRouteFilterTrains = null; // fallback 不做路線過濾
            } else {
                activeRouteFilterTrains = filteredTrainNos;
            }
        }

        if (activeRouteFilterTrains !== previousFilterState) {
            if (typeof redrawAll === 'function') redrawAll();
        }

        // 1. 先取得使用者現在的本地時間 (轉換成當天分鐘數)
        const currentMinutes = getCurrentSystemMinutes();

        searchData.sort((a, b) => {
            // 優先比對分數
            if (b.score !== a.score) return b.score - a.score; 

            // 如果都有出發時間，進行「智能環狀時間排序」
            if (a.startTime !== undefined && b.startTime !== undefined) {
                
                // 🌟 核心魔法：如果這班車的發車時間「小於現在時間」，
                // 代表今天這班車已經開走了！我們將它偷偷 +1440，把它推到「明天」去排隊。
                // (如果它本來就已經是大於 1440 的跨夜車，就不受影響)
                let sortTimeA = a.startTime < currentMinutes ? a.startTime + 1440 : a.startTime;
                let sortTimeB = b.startTime < currentMinutes ? b.startTime + 1440 : b.startTime;

                return sortTimeA - sortTimeB;
            }

            // 保底機制：比對字串長度
            let aStr = a.type === 'station' ? a.name : a.id;
            let bStr = b.type === 'station' ? b.name : b.id;
            return aStr.length - bStr.length;
        });
        // --- 渲染結果 ---
        if (searchData.length > 0) {
            let resultsHtml = searchData.map(item => {
                if (item.type === 'station') {
                    return `<div class="search-item selectable-item" onclick="triggerSearchSelect('station', '${item.id}', this)"><span class="search-item-badge badge-station">車站</span> <span>${item.name}</span><span style="opacity: 0.5; font-size: 13px; margin-left: 8px; font-family: monospace;">(${item.id})</span></div>`;
                } else {
                    let routeBadge = keywords.length >= 2 ? `<span style="font-size: 12px; color: #FFA500; margin-left: 8px;">(直達)</span>` : "";
                    
                    // 🌟 核心升級：同時讀取 Type 和 ID 的顯示設定
                    let currentShowType = !(settings && settings.show_train_type === false);
                    let trainLabel = currentShowId ? "車次" : "列車";
                    
                    let displayParts = [];
                    if (currentShowType && item.typeStr) displayParts.push(item.typeStr);
                    if (currentShowId && item.id) {
                        let dispIdStr = item.displayNo || item.dispId || item.id;
                        dispIdStr = String(dispIdStr).replace(/\|[^ ]+/g, '');
                        displayParts.push(dispIdStr);
                    }
                    let trainDisplayText = displayParts.join(' ');
                    // 起訖站備註（有 display_no 代行班次、或多班同號時區分用）
                    let staAnnotation = (item.startSta || item.endSta)
                        ? `<span style="font-size:11px;opacity:0.5;margin-left:4px;">${item.startSta}→${item.endSta}</span>`
                        : "";
                    
                    let timeHtml = "";
                    if (item.startTime !== undefined && item.endTime !== undefined) {
                        let fStart = formatTimeDisplay(item.startTime);
                        let fEnd = formatTimeDisplay(item.endTime);
                        timeHtml = `<span style="font-size: 13px; opacity: 0.8; margin-left: auto; font-family: monospace;">${fStart} ➔ ${fEnd}</span>`;
                    }

                    return `<div class="search-item selectable-item" style="display: flex; align-items: center;" onclick="triggerSearchSelect('train', '${item.id}', this)">
                        <span class="search-item-badge badge-train">${trainLabel}</span>
                        <span style="margin-right: 4px;">${trainDisplayText}</span>${staAnnotation}
                        ${routeBadge}
                        ${timeHtml}
                    </div>`;
                }
            });
            searchResults.innerHTML = resultsHtml.join('');
        } else {
            let notFoundText = keywords.length >= 2 ? "找不到符合方向的直達車" : (currentShowId ? "找不到相符的車站或車次" : "找不到相符的車站");
            searchResults.innerHTML = `<div class="search-item" style="color: #888; justify-content: center; cursor: default;">${notFoundText}</div>`;
        }
        
        searchResults.style.display = 'block';
    });

    // --- 攔截鍵盤事件 (上下鍵與智慧 Enter) ---
    searchInput.addEventListener('keydown', (e) => {
        let items = searchResults.querySelectorAll('.selectable-item');

        // 🌟 智慧 Enter 邏輯
        if (e.key === "Enter") {
            e.preventDefault(); // 防止表單預設送出

            let rawText = searchInput.value.trim();
            let keywords = normalizeText(rawText).split(/[~\-\s,，、]+/).filter(k => k.length > 0);

            // 判斷是否為區間搜尋（至少一個關鍵字符合拓樸站名）
            let isRouteSearch = false;
            if (keywords.length >= 2) {
                if (topology && topology.segments) {
                    isRouteSearch = keywords.some(k =>
                        topology.segments.some(seg =>
                            seg.stations.some(st => normalizeText(st.name || "").includes(k))
                        )
                    );
                } else {
                    isRouteSearch = /[~\-,，、]/.test(rawText);
                }
                if (isRouteSearch) {
                    SearchHistoryManager.add({
                        type: 'route',
                        id: rawText,
                        keyword: rawText,
                        displayHtml: `<span class="search-item-badge" style="background: #FFA500; color: #000;">區間</span> <span style="margin-left: 8px;">${rawText}</span>`
                    });
                }
            }

            // 狀況 A：選單是隱藏的 → 觸發新搜尋（不顯示可能過期的舊內容）
            if (searchResults.style.display === 'none') {
                searchInput.dispatchEvent(new InputEvent('input', { bubbles: true }));
                return;
            }
            // 狀況 B：選單已開著 → 執行選取動作
            else {
                if (currentFocus > -1) {
                    if (items[currentFocus]) items[currentFocus].click();
                }
                else if (items.length > 0 && !isRouteSearch) {
                    // 區間搜尋時不自動選第一班車，讓使用者用方向鍵選擇
                    items[0].click();
                }
            }
        } 
        // 🌟 上下鍵邏輯 (只有在選單開啟時才生效)
        else {
            if (searchResults.style.display === 'none' || items.length === 0) return;

            if (e.key === "ArrowDown") {
                e.preventDefault(); 
                currentFocus++; 
                addActive(items);
            } else if (e.key === "ArrowUp") {
                e.preventDefault(); 
                currentFocus--; 
                addActive(items);
            }
        }
    });

    function addActive(items) {
        if (!items) return false;
        removeActive(items);
        if (currentFocus >= items.length) currentFocus = 0;
        if (currentFocus < 0) currentFocus = (items.length - 1);
        items[currentFocus].classList.add("search-item-active");
        items[currentFocus].scrollIntoView({ block: 'nearest' });
    }
    function removeActive(items) { for (let i = 0; i < items.length; i++) items[i].classList.remove("search-item-active"); }
}

// ==========================================
// 🌟 供搜尋面板專用的全域觸發器 (支援歷史紀錄版)
// ==========================================
window.triggerSearchSelect = function(type, id, element, saveHistory = true) {
    const searchResults = document.getElementById('search-results');
    if (searchResults) searchResults.style.display = 'none';

    // 🌟 1. 存入歷史紀錄，並同步輸入框文字
    if (saveHistory) {
        let keyword = "";
        let displayHtml = "";
        
        if (type === 'station') {
            let stName = getStationName(id);
            keyword = stName;
            displayHtml = `<span class="search-item-badge badge-station">車站</span> <span style="margin-left: 8px;">${stName}</span>`;
        } else if (type === 'train') {
            let targetTrain = timetable.find(t => String(t.no || t.train_no || t.id) === String(id));
            if (targetTrain) {
                let historyData = window.buildTrainHistoryData(targetTrain);
                keyword = historyData.keyword;
                displayHtml = historyData.displayHtml;
            } else {
                keyword = id;
                displayHtml = `<span class="search-item-badge badge-train">車次</span> <span style="margin-left: 8px;">${id}</span>`;
            }
        }
        
        SearchHistoryManager.add({ type, id, keyword, displayHtml });
        window.updateSearchInputText(keyword);
    }

    // 2. 執行跳轉與選取
    if (type === 'station') {
        if (typeof window.triggerSelectStation === 'function') {
            window.triggerSelectStation(id);
        }
    } else if (type === 'train') {
        let targetTrain = timetable.find(t => String(t.no || t.train_no || t.id) === String(id));
        if (targetTrain && !activeTrainTypes.has(targetTrain.type)) {
            activeTrainTypes.add(targetTrain.type);
            document.querySelectorAll('#train-type-container .pill-btn').forEach(b => {
                if(b._updateStyle) b._updateStyle();
            });
        }
        if (typeof window.triggerSelectTrain === 'function') {
            window.triggerSelectTrain(id, false); // history already saved above
        }
    }
};

// ==========================================
// 🖱️ 底部面板：滑鼠滾輪與手機左右滑動切換 (無衝突整合版)
// ==========================================
function setupBottomBarScrolling() {
    const bottomBar = document.getElementById('bottom-bar');
    if (!bottomBar) return;

    // --- 1. 原本的滑鼠滾輪轉換邏輯 (維持不變) ---
    // 讓電腦版使用者可以用滾輪左右查看長長的車站列表
    bottomBar.addEventListener('wheel', (e) => {
        const scrollContainer = document.getElementById('bottom-scroll-container');
        if (scrollContainer) {
            e.preventDefault(); 
            e.stopPropagation(); 
            scrollContainer.scrollLeft += (e.deltaY * 1.5); 
        }
    }, { passive: false });

    // --- 2. 🌟 新增：手機端的手勢偵測 (Swipe Gesture) ---
    let touchStartX = 0;
    let touchStartY = 0;

    bottomBar.addEventListener('touchstart', (e) => {
        // 如果是雙指縮放，不介入
        if (e.touches.length > 1) return;
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
    }, { passive: true });

    bottomBar.addEventListener('touchend', (e) => {
        // 🛡️ 核心防護網 A：如果是在看「車站」，讓原生 CSS 去滑動，我們 JS 絕對不插手！
        if (selectedStation) return; 

        // 🛡️ 核心防護網 B：如果根本沒有選中火車，也不做事
        if (!selectedTrain) return;

        let touchEndX = e.changedTouches[0].clientX;
        let touchEndY = e.changedTouches[0].clientY;

        let deltaX = touchEndX - touchStartX;
        let deltaY = touchEndY - touchStartY;

        // 判斷是否為「明確的水平滑動」(水平位移 > 50px 且大於垂直位移)
        if (Math.abs(deltaX) > 50 && Math.abs(deltaX) > Math.abs(deltaY)) {
            
            // 抓出這台車所有的關聯車次 (直通 或 併結)
            let partners = selectedTrain.coupled_with ? selectedTrain.coupled_with.filter(c => c.action === 'split' || c.action === 'direct') : [];
            
            if (partners.length > 0) {
                // 如果只有一台伴侶車 (大部分新幹線的狀況)，不管左右滑都直接切過去
                if (partners.length === 1) {
                    window.switchTrainKeepView(partners[0].train_id);
                } 
                // 如果未來有「三車併結」等狀況，利用 deltaX 正負值決定方向
                else {
                    let targetIndex = deltaX < 0 ? 1 : 0; 
                    if (partners[targetIndex]) {
                        window.switchTrainKeepView(partners[targetIndex].train_id);
                    }
                }
            }
        }
    }, { passive: true });
}

// ==========================================
// 🌟 視窗與容器大小改變處理 (ResizeObserver 終極版)
// ==========================================
let resizeTimeout;
const canvasWrapperElement = document.getElementById('canvas-wrapper');

if (canvasWrapperElement) {
    // 建立一個變形監視器
    const resizeObserver = new ResizeObserver(entries => {
        clearTimeout(resizeTimeout);
        
        // 加上 150 毫秒的防抖，確保手機網址列縮放或排版完全穩定後才重繪
        resizeTimeout = setTimeout(() => {
            const rect = entries[0].contentRect;

            // 防呆：如果寬度或高度是 0 (例如切換頁面被隱藏)，不浪費效能
            if (rect.width === 0 || rect.height === 0) return;

            // 🌟 核心：在這裡抓取高畫質！這時候的物理像素絕對是 100% 完美的！
            initCanvas('diaCanvas', 'canvas-wrapper');

            // 🌟 resize 一律不重新 autoFitScale。
            // 開關底部面板/側欄、甚至手機網址列伸縮，都只是改變容器大小，不該重新適配比例：
            //   舊行為會把 scaleX 縮小 → 大型路線(JR西日本)整條時間軸縮到比螢幕窄
            //   → clampCamera 判定內容比螢幕窄 → 強制 camera.x 貼最左 → 運行圖跳到 0:00、且縮小。
            // （手機網址列會改變 window.innerHeight，所以「視窗有沒有變」無法可靠分辨面板開關，
            //   故乾脆完全不在 resize 重新 fit。初次載入 init 與切換路線 handleRouteSwitch 會各自做 fit。）
            // 保留使用者目前的 scaleX/scaleY 與鏡頭位置，只重新校正邊界並重繪。
            if (typeof clampCamera === 'function') clampCamera();
            if (typeof redrawAll === 'function') redrawAll();
        }, 150); 
    });

    // 啟動監視！死死盯著畫布的容器
    resizeObserver.observe(canvasWrapperElement);
}

// 保留 window.resize 僅作為極端狀況的備用
window.addEventListener('resize', () => {
    // 主要工作已經交給 ResizeObserver 了，這裡可以安心留空
});

// 統整重繪動作
function redrawAll() {
    clampCamera();
    
    camera.x = Math.round(camera.x);
    camera.y = Math.round(camera.y);

    // ==========================================
    // 🌟 終極防禦：不管前面狀態多混亂，強制把矩陣歸零、徹底洗淨實體畫布！
    // ==========================================
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(1, 0, 0, 1, 0, 0);               // 1. 矩陣歸零 (回到最原始物理座標)
    ctx.clearRect(0, 0, canvas.width, canvas.height); // 2. 怒清整個物理畫布，保證零殘影
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);           // 3. 重新開啟高畫質縮放
    
    // 1. 先畫最底層：網格線
    drawGrid(currentRouteView, 'lines'); 
    
    // 2. 中間層：畫火車線
    drawTrains();
    
    // 3. 最上層：畫站名與時間標籤
    drawGrid(currentRouteView, 'labels');
    
    // 4. 現在時間的紅線
    drawCurrentTimeLine();      
}

// ==========================================
// 綁定主題切換功能
// ==========================================
function bindThemeToggle() {

    // 🌟 1. 防呆鎖：如果已經綁定過了，就直接退堂，不要再綁第二次！
    if (isThemeBound) return; 
    
    // 🌟 2. 標記為已綁定
    isThemeBound = true;

    const btnTheme = document.getElementById('btn-theme');

    // 🌟 新增：先抓到 HTML 裡面的 flatpickr CSS 標籤
    // (⚠️ 請確保你的 index.html 裡那行 CSS 有加上 id="flatpickr-theme")
    const flatpickrThemeLink = document.getElementById('flatpickr-theme');

    btnTheme.addEventListener('click', () => {
        isDarkMode = !isDarkMode;
        
        btnTheme.textContent = isDarkMode ? "🌞" : "🌙";

        // 🌟 核心新增：給 body 貼上/撕下 light-mode 標籤，並同步切換日曆主題！
        if (isDarkMode) {
            document.body.classList.remove('light-mode'); // 撕下標籤 (恢復深色模式)
            
            // 🌟 將日曆切換回「暗黑主題」
            if (flatpickrThemeLink) {
                flatpickrThemeLink.href = "https://npmcdn.com/flatpickr/dist/themes/dark.css";
            }
        } else {
            document.body.classList.add('light-mode');    // 貼上標籤 (觸發淺色模式)
            
            // 🌟 將日曆切換為「淺色預設主題」
            if (flatpickrThemeLink) {
                flatpickrThemeLink.href = "https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css";
            }
        }
        
        // 1. 切換畫布容器與側邊欄的背景顏色
        document.getElementById('canvas-wrapper').style.backgroundColor = isDarkMode ? "#000000" : "#FFFFFF";
        document.getElementById('sidebar').style.backgroundColor = isDarkMode ? "#333333" : "#D2D2D2";
        document.getElementById('sidebar').style.color = isDarkMode ? "#FFFFFF" : "#000000";
        document.querySelectorAll('.control-section h3').forEach(h3 => {
            h3.style.color = isDarkMode ? "#FFFFFF" : "#000000";
        });

        // 🌟 2. 統一更新那 5 顆「靜態工具按鈕」的底色
        let defaultBg = isDarkMode ? "#444444" : "#E0E0E0";
        let defaultBorder = isDarkMode ? "#555555" : "#CCCCCC";
        let defaultText = isDarkMode ? "#CCCCCC" : "#000000";

        document.querySelectorAll('#sidebar .pill-btn').forEach(btn => {
            // 排除路線按鈕與車種按鈕 (車種按鈕有綁定 _updateStyle)，剩下的就是那 5 顆！
            if (!btn.closest('#route-type-container') && !btn._updateStyle) {
                btn.style.backgroundColor = defaultBg;
                btn.style.borderColor = defaultBorder;
                btn.style.color = defaultText;
            }
        });
        
        // 3. 觸發所有「動態按鈕」重新讀取日/夜色碼
        if (window.updateRouteButtons) window.updateRouteButtons();
        document.querySelectorAll('#train-type-container .pill-btn').forEach(btn => {
            if(btn._updateStyle) btn._updateStyle();
        });
        // 同步更新群組全選/全取消按鈕樣式
        if (window._allGroupUpdateFns) window._allGroupUpdateFns.forEach(fn => fn());

        // ==========================================
        // 🌟 核心修復：在重新渲染面板前，先「記住」目前的展開狀態與滾動進度！
        // ==========================================
        const panel = document.getElementById('bottom-bar');
        const isExpanded = panel ? panel.classList.contains('expanded') : false; 

        const scrollContainer = document.getElementById('bottom-scroll-container');
        let savedScrollLeft = scrollContainer ? scrollContainer.scrollLeft : 0;
        let savedScrollTop = scrollContainer ? scrollContainer.scrollTop : 0; // 🌟 補上這行：記住「上下」滾動進度！

        if (selectedStation) {
            updateBottomPanelStation(selectedStation);
        }
        else if (selectedTrain) {
            updateBottomPanel(selectedTrain);
        }

        // ==========================================
        // 🌟 重新抓取剛畫好的新面板，把展開狀態與滾動進度「還給」它！
        // ==========================================
        const newPanel = document.getElementById('bottom-bar');
        if (newPanel && isExpanded) {
            newPanel.classList.add('expanded'); 
        }

        const newScrollContainer = document.getElementById('bottom-scroll-container');
        if (newScrollContainer) {
            newScrollContainer.scrollLeft = savedScrollLeft;
            newScrollContainer.scrollTop = savedScrollTop; // 🌟 補上這行：還原「上下」滾動進度！
        }

        // 4. 重繪畫布
        redrawAll();
    });
}

// ==========================================
// 🌟 視角自動適應 (完美結合環狀防護網與無極限拉伸)
// ==========================================
function autoFitScale() {
    const wrapper = document.getElementById('canvas-wrapper');
    if (!wrapper || typeof loopKm === 'undefined' || loopKm <= 0) return;

    let presetKey = currentRouteView; 
    let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
    
    // 🌟 1. 讀取自訂拉伸比例 (預設 1.0)
    let customRatio = settings?.view_presets?.[presetKey]?.stretch_ratio || 1.0;

    let targetScaleY = 2.0; 

    // 🌟 2. 重新計算基礎 Y 軸比例
    if (isCircular) {
        // 環狀線不需要被強迫撐滿螢幕！給它一個舒適的預設值。
        // 大阪環狀線會因為這樣，自然地在螢幕上呈現出 2~3 圈的完美循環。
        targetScaleY = 15.0 * customRatio;
    } else {
        // 直線路線：剛好佔滿畫面 90%
        targetScaleY = ((wrapper.clientHeight * 0.9) / loopKm) * customRatio;
    }

    if (settings?.view_presets?.[presetKey]?.default_scale_y !== undefined) {
        targetScaleY = settings.view_presets[presetKey].default_scale_y;
    }

    CONFIG.scaleY = Math.min(Math.max(targetScaleY, 0.5), 100);

    // 🌟 3. 處理 X 軸 (時間軸) 比例，維持優雅的傾斜度
    let timeStretchRatio = 0.4;
    if (settings && settings.time_stretch_ratio !== undefined) {
        timeStretchRatio = settings.time_stretch_ratio;
    }
    if (settings?.view_presets?.[presetKey]?.time_stretch_ratio !== undefined) {
        timeStretchRatio = settings.view_presets[presetKey].time_stretch_ratio;
    }

    CONFIG.scaleX = CONFIG.scaleY * timeStretchRatio;

    // 🌟 4. 核心防護：徹底移除「強迫 26 小時塞進螢幕」的毒瘤！
    // 讓使用者可以自由橫向滾動，不再把火車擠成垂直線！
    const _minScaleX = (wrapper.clientWidth * 0.75 - CONFIG.paddingLeft) / 1560;

    if (_minScaleX > 0 && CONFIG.scaleX < _minScaleX) {
        CONFIG.scaleX = _minScaleX;
    }

    CONFIG.scaleY_fit = CONFIG.scaleY;
    CONFIG.scaleX_fit = CONFIG.scaleX;
}

// ==========================================
// 🌟 車站全網雷達：找出「真正有畫出該車站」的路線 (防區間截取Bug版)
// ==========================================
function findPresetsForStation(stationKeyword) {
    let foundPresets = [];

    for (const [presetKey, presetData] of Object.entries(settings.view_presets)) {
        let hasStation = false;
        let selectedSegments = presetData.lines || [];

        // 🌟 使用智慧整理器，精準過濾掉被截斷的車站
        let segmentsData = getProcessedSegments(selectedSegments, topology);

        segmentsData.forEach(data => {
            let stationsToDraw = data.stations;
            if (stationsToDraw.some(st => st.name === stationKeyword || st.id === stationKeyword)) {
                hasStation = true;
            }
        });

        if (hasStation) {
            foundPresets.push({
                id: presetKey,
                name: presetData.name
            });
        }
    }
    
    return foundPresets;
}

// ==========================================
// 🌟 智慧視角跳轉：雙軸精準對焦 + 座標雷達版
// ==========================================
function focusStationOnCanvas(stationId, stationName, targetMinutes = null) {
    if (!lookupY[stationId] || lookupY[stationId].length === 0) {
        let availableRoutes = findPresetsForStation(stationId);
        if (!availableRoutes || availableRoutes.length === 0) {
            availableRoutes = findPresetsForStation(stationName);
        }

        if (!availableRoutes || availableRoutes.length === 0) return;

        let targetRoute = availableRoutes[0];
        if (targetRoute.id === currentRouteView) {
            if (availableRoutes.length > 1) targetRoute = availableRoutes[1]; 
            else return; 
        }

        handleRouteSwitch(targetRoute.id);
        focusStationOnCanvas(stationId, stationName, targetMinutes);
        return; 
    }

    let targetY = lookupY[stationId][0].y;
    const wrapper = document.getElementById('canvas-wrapper');
    let screenH = wrapper ? wrapper.clientHeight : canvas.height;
    let screenW = wrapper ? wrapper.clientWidth : canvas.width;
    
    camera.y = Math.round(targetY - (screenH / 2));

    if (targetMinutes !== null) {
        let targetX = timeToX(targetMinutes);
        camera.x = Math.round(targetX - (screenW / 2));
    }

    clampCamera();
    checkInfiniteScroll();

    requestAnimationFrame(() => {
        redrawAll();
    });
}
// ==========================================
// 核心限制函數：禁止攝影機滑出邊界 (包含上下黑洞防護)
// ==========================================
function clampCamera() {
    const wrapper = document.getElementById('canvas-wrapper');
    if (!wrapper) return;
    const wrapperW = wrapper.clientWidth;
    const wrapperH = wrapper.clientHeight; // 🌟 記得抓取螢幕高度

    // --- X 軸限制 (左右) ---
    const contentWidth = 1560 * CONFIG.scaleX;
    const minX = CONFIG.paddingLeft - SIDE_MARGIN;
    const maxX = CONFIG.paddingLeft + contentWidth - wrapperW + SIDE_MARGIN;

    if (contentWidth + (SIDE_MARGIN * 2) < wrapperW) {
        camera.x = minX; 
    } else {
        if (camera.x < minX) camera.x = minX;
        if (camera.x > maxX) camera.x = maxX;
    }

    // --- 🌟 Y 軸限制 (上下，防止出現巨大留空) ---
    let presetKey = currentRouteView; 
    let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
    
    if (!isCircular) {
        const contentHeight = loopKm * CONFIG.scaleY;
        const minY = -50; // 允許畫布頂端多 50px 留白 (剛好放時間標籤)
        const maxY = CONFIG.paddingTop + contentHeight - wrapperH + 50;

        // 如果地圖的高度比你的螢幕還要矮
        if (contentHeight + 100 < wrapperH) {
            camera.y = minY; // 強制貼齊上方，不准亂跑
        } else {
            // 如果地圖很高，就執行上下撞牆限制
            if (camera.y < minY) camera.y = minY;
            if (camera.y > maxY) camera.y = maxY;
        }
    }
}

// ==========================================
// 瞬移補償：讓攝影機永遠保持在「中間那一圈」
// ==========================================
function checkInfiniteScroll() {
    if (!(loopHeight > 0)) return;

    let presetKey = currentRouteView; 
    let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
    if (!isCircular) return;

    const centerPoint = CONFIG.paddingTop + loopHeight;

    // 🌟 核心升級：不管偏離多遠，直接用數學計算偏差圈數，瞬間拉回中間！
    let diff = camera.y - centerPoint;
    let offsetCopies = Math.round(diff / loopHeight);
    
    if (offsetCopies !== 0) {
        camera.y -= offsetCopies * loopHeight;
    }
    
    camera.y = Math.round(camera.y);
}

// ==========================================
// 💻 電腦滑鼠 + 📱 手機觸控 (分流雙軌最穩版)
// ==========================================
function setupCanvasInteractions() {
    const wrapper = document.getElementById('canvas-wrapper');
    const canvas = document.getElementById('diaCanvas');
    if (!wrapper || !canvas) return;

    // 🌟 核心防修復：如果已經綁定過，就直接退場，不要重複綁定到 window 上！
    if (isInteractionsBound) return; 
    isInteractionsBound = true;

    // 嚴格禁止手機原生滑動與雙擊放大
    wrapper.style.touchAction = 'none';

    let isDragging = false;
    let startMouseX = 0, startMouseY = 0;
    let startCameraX = 0, startCameraY = 0;

    // ==========================================
    // 🛠️ 共用邏輯：計算縮放
    // ==========================================
    const applyZoom = (zoom, mouseX, mouseY) => {
        const wrapperW = wrapper.clientWidth;
        const wrapperH = wrapper.clientHeight;
        const currentCamX = Math.round(camera.x);
        const currentCamY = Math.round(camera.y);

        const dataX = (currentCamX + mouseX - CONFIG.paddingLeft) / CONFIG.scaleX;
        const dataY = (currentCamY + mouseY - CONFIG.paddingTop) / CONFIG.scaleY;

        let safeLoopKm = (typeof loopKm !== 'undefined' && loopKm > 0) ? loopKm : 1;
        let safeMargin = (typeof SIDE_MARGIN !== 'undefined') ? SIDE_MARGIN : 0;

        // ==========================================
        // 🌟 修復三：防呆極限，防止縮太小導致寬度變負數，畫面崩潰
        // ==========================================
        let availableWidth = Math.max(wrapperW - safeMargin * 2, 400); 
        const minScaleX = availableWidth / 1560;

        let presetKey = currentRouteView;
        let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";

        // 🌟 徹底解除環狀線的縮小封印！
        // 讓所有路線都能自由縮小到最初適應比例的 20% (可以看到好幾圈)
        const minScaleY = (CONFIG.scaleY_fit && CONFIG.scaleY_fit > 0)
            ? CONFIG.scaleY_fit * 0.2
            : (wrapperH / 2) / safeLoopKm;

        if (zoom < 1) {
            let minAllowedZoom = Math.max(minScaleX / CONFIG.scaleX, minScaleY / CONFIG.scaleY);
            if (minAllowedZoom > 1) minAllowedZoom = 1;
            if (zoom < minAllowedZoom) zoom = minAllowedZoom;
        }

        CONFIG.scaleX *= zoom;
        CONFIG.scaleY *= zoom;

        let targetX = (CONFIG.paddingLeft + dataX * CONFIG.scaleX) - mouseX;
        let targetY = (CONFIG.paddingTop + dataY * CONFIG.scaleY) - mouseY;

        const minLimitX = CONFIG.paddingLeft - safeMargin;
        const contentWidth = 1560 * CONFIG.scaleX;
        const maxLimitX = CONFIG.paddingLeft + contentWidth - wrapperW + safeMargin;

        if (contentWidth + (safeMargin * 2) <= wrapperW + 1) {
            camera.x = minLimitX;
        } else {
            camera.x = Math.max(minLimitX, Math.min(targetX, maxLimitX));
        }

        camera.y = targetY;
        camera.x = Math.round(camera.x);
        camera.y = Math.round(camera.y);

        if (typeof loopKm !== 'undefined' && loopKm > 0) loopHeight = loopKm * CONFIG.scaleY;
        if (typeof checkInfiniteScroll === 'function') checkInfiniteScroll();
        
        if (typeof requestRedraw === 'function') requestRedraw();
        else if (typeof redrawAll === 'function') redrawAll();
    };

    // ==========================================
    // 🎯 共用邏輯：點擊判定
    // ==========================================
    const executeClick = (clientX, clientY) => {
        const rect = canvas.getBoundingClientRect();
        const worldX = (clientX - rect.left) + camera.x;
        const worldY = (clientY - rect.top) + camera.y;
        const wrapperW = wrapper.clientWidth;

        let closestTrain = null, minDistance = 15; 

        // --- 1. 掃描火車 ---
        if (typeof timetable !== 'undefined') {
            for (let train of timetable) {
                if (typeof activeTrainTypes !== 'undefined' && !activeTrainTypes.has(train.type)) continue;

                if (selectedStation) {
                    let stopsHere = false;
                    if (train.segments) {
                        for (let seg of train.segments) {
                            for (let i = 0; i < seg.s.length; i++) {
                                if (String(seg.s[i]) === String(selectedStation) && seg.v[i] !== 2) {
                                    stopsHere = true; break;
                                }
                            }
                            if (stopsHere) break;
                        }
                    }
                    if (!stopsHere) continue; 
                }

                if (!train._hitPoints) continue;
                for (let i = 0; i < train._hitPoints.length - 1; i++) {
                    let p1 = train._hitPoints[i], p2 = train._hitPoints[i+1];
                    if (!p1 || !p2) continue;
                    let dist = getDistanceToSegment(worldX, worldY, p1.x, p1.y, p2.x, p2.y);
                    if (dist < 15 && dist < minDistance) { 
                        minDistance = dist; 
                        closestTrain = train; 
                    }
                }
            }
        }

        // --- 2. 🌟 精準掃描車站 (區分「橫線」與「文字框」) ---
        let closestStationLineId = null; 
        let closestStationTextId = null;
        let minStationDist = 12; 
        let isCircular = settings?.view_presets?.[currentRouteView]?.view_type === "CIRCULAR";
        if (typeof lookupY !== 'undefined') {
            // 借用畫筆來測量站名文字的真實寬度
            const tempCtx = canvas.getContext('2d');
            tempCtx.font = "bold 16px 'GlowSans', sans-serif";
            const { copyStart, copyEnd } = isCircular
                ? getCircularCopyRange(loopHeight, camera.y - 100, camera.y + wrapper.clientHeight + 100)
                : { copyStart: 0, copyEnd: 0 };

            for (let st_id in lookupY) {
                let stName = getStationName(st_id);
                let textWidth = tempCtx.measureText(stName).width; // 量測文字寬度

                for (let opt of lookupY[st_id]) {
                    for (let copy = copyStart; copy <= copyEnd; copy++) {
                        let offsetY = isCircular ? ((copy * loopHeight) + CONFIG.paddingTop + loopHeight) : CONFIG.paddingTop;
                        let stationY = opt.y + offsetY;
                        
                        // 偵測 A：是否點在車站橫線上
                        if (Math.abs(worldY - stationY) < minStationDist) {
                            minStationDist = Math.abs(worldY - stationY);
                            closestStationLineId = st_id;
                        }

                        // 偵測 B：是否「精準」點擊在浮動文字框內！(高度容錯給 15px)
                        if (Math.abs(worldY - stationY) <= 15) {
                            // 左側文字座標範圍
                            let labelXLeft = Math.max(0, camera.x + 10);
                            let leftBound = labelXLeft - 5;
                            let rightBound = labelXLeft + textWidth + 15;

                            const rX = camera.x + wrapperW - 10;
                            const hitRight = worldX >= rX - textWidth - 15 && worldX <= rX + 5;
                            if ((worldX >= leftBound && worldX <= rightBound) || hitRight) {
                                closestStationTextId = st_id;
                            }
                        }
                    }
                }
            }
        }

        // --- 3. 🌟 終極權重裁決 ---
        if (closestStationTextId) {
            selectedStation = closestStationTextId; 
            selectedTrain = null;
            let stName = getStationName(closestStationTextId);
            window.updateSearchInputText(stName); // 🌟 同步文字
            // 🌟 寫入歷史紀錄
            SearchHistoryManager.add({ type: 'station', id: closestStationTextId, keyword: stName, displayHtml: `<span class="search-item-badge badge-station">車站</span> <span style="margin-left: 8px;">${stName}</span>` });
            if (typeof updateBottomPanelStation === 'function') updateBottomPanelStation(selectedStation);

        } else if (closestTrain) {
            // 🌟 核心修復：不再走捷徑！統一交給正規引擎，並開啟防跳動(true)
            let tNo = closestTrain.no || closestTrain.train_no || closestTrain.id;
            window.triggerSelectTrain(tNo, true, true);

        } else if (closestStationLineId) {
            selectedStation = closestStationLineId; 
            selectedTrain = null;
            let stName = getStationName(closestStationLineId);
            window.updateSearchInputText(stName); // 🌟 同步文字
            // 🌟 寫入歷史紀錄
            SearchHistoryManager.add({ type: 'station', id: closestStationLineId, keyword: stName, displayHtml: `<span class="search-item-badge badge-station">車站</span> <span style="margin-left: 8px;">${stName}</span>` });
            if (typeof updateBottomPanelStation === 'function') updateBottomPanelStation(selectedStation);

        } else {
            selectedTrain = null; 
            selectedStation = null;
            if (activeRouteFilterTrains === null) {
                window.updateSearchInputText(''); 
            }
            if (typeof updateBottomPanel === 'function') updateBottomPanel(null);
        }

        if (typeof redrawAll === 'function') redrawAll();
    };

    // ==========================================
    // 💻 [電腦專區] 標準滑鼠事件 (Mouse)
    // ==========================================
    wrapper.addEventListener('mousedown', (e) => {
        isDragging = true;
        startMouseX = e.clientX; startMouseY = e.clientY;
        startCameraX = camera.x; startCameraY = camera.y;
        wrapper.style.cursor = 'grabbing';
    });

    // ==========================================
    // 💻 [電腦版專區] 滑鼠移動事件 (包含拖曳與 Hover 偵測)
    // ==========================================
    window.addEventListener('mousemove', (e) => { 
        if (isDragging) {
            camera.x = startCameraX - (e.clientX - startMouseX);
            camera.y = startCameraY - (e.clientY - startMouseY);
            if (typeof clampCamera === 'function') clampCamera();
            if (typeof requestRedraw === 'function') requestRedraw();
            else redrawAll();
        } else if (e.target === canvas || e.target === wrapper) {
            
            const rect = wrapper.getBoundingClientRect();
            const worldX = (e.clientX - rect.left) + camera.x;
            const worldY = (e.clientY - rect.top) + camera.y;
            const wrapperW = wrapper.clientWidth;

            let hitTrain = null;
            
            // --- 1. 偵測火車 ---
            for (let train of timetable) {
                if (selectedStation) {
                    let stopsHere = false;
                    if (train.segments) {
                        for (let seg of train.segments) {
                            for (let i = 0; i < seg.s.length; i++) {
                                if (String(seg.s[i]) === String(selectedStation) && seg.v[i] !== 2) {
                                    stopsHere = true; break;
                                }
                            }
                            if (stopsHere) break;
                        }
                    }
                    if (!stopsHere) continue; 
                }

                if (!train._hitPoints || train._hitPoints.length < 2) continue; 
                for (let i = 0; i < train._hitPoints.length - 1; i++) {
                    let p1 = train._hitPoints[i], p2 = train._hitPoints[i+1];
                    if (!p1 || !p2) continue; 
                    let dist = getDistanceToSegment(worldX, worldY, p1.x, p1.y, p2.x, p2.y);
                    if (dist < 6) {
                        hitTrain = train; break; 
                    }
                }
                if (hitTrain) break; 
            }

            // --- 2. 🌟 精準偵測車站 (文字框 vs 橫線) ---
            let hitStationLine = null;
            let hitStationText = null;
            let minStationDist = 12; 
            let isCircular = settings?.view_presets?.[currentRouteView]?.view_type === "CIRCULAR";
            if (typeof lookupY !== 'undefined') {
                const tempCtx = canvas.getContext('2d');
                tempCtx.font = "bold 16px 'GlowSans', sans-serif";
                const { copyStart, copyEnd } = isCircular
                    ? getCircularCopyRange(loopHeight, camera.y - 100, camera.y + wrapper.clientHeight + 100)
                    : { copyStart: 0, copyEnd: 0 };

                for (let st_id in lookupY) {
                    let stName = getStationName(st_id);
                    let textWidth = tempCtx.measureText(stName).width;

                    for (let opt of lookupY[st_id]) {
                        for (let copy = copyStart; copy <= copyEnd; copy++) {
                            let offsetY = isCircular ? ((copy * loopHeight) + CONFIG.paddingTop + loopHeight) : CONFIG.paddingTop;
                            let stationY = opt.y + offsetY;
                            
                            // A. 滑鼠碰到車站橫線
                            if (Math.abs(worldY - stationY) < minStationDist) {
                                minStationDist = Math.abs(worldY - stationY);
                                hitStationLine = st_id;
                            }

                            // B. 滑鼠精準碰到站名文字框
                            if (Math.abs(worldY - stationY) <= 15) {
                                let labelXLeft = Math.max(0, camera.x + 10);
                                let leftBound = labelXLeft - 5;
                                let rightBound = labelXLeft + textWidth + 15;

                                const rX2 = camera.x + wrapperW - 10;
                                const hitRight2 = worldX >= rX2 - textWidth - 15 && worldX <= rX2 + 5;
                                if ((worldX >= leftBound && worldX <= rightBound) || hitRight2) {
                                    hitStationText = st_id;
                                }
                            }
                        }
                    }
                }
            }

            // --- 3. 🌟 權重裁決 ---
            let finalHitTrain = null;
            let finalHitStation = null;

            if (hitStationText) {
                // 滑鼠在站名字體上方 -> 絕對車站優先 (無視火車線)
                finalHitStation = hitStationText;
            } else if (hitTrain) {
                // 滑鼠在圖表區，碰到火車 -> 火車優先
                finalHitTrain = hitTrain;
            } else if (hitStationLine) {
                // 滑鼠在圖表區，沒碰到火車 -> 橫線優先
                finalHitStation = hitStationLine;
            }

            // --- 4. 狀態更新與重繪 ---
            let statusChanged = false;
            if (finalHitTrain !== hoveredTrain) { hoveredTrain = finalHitTrain; statusChanged = true; }
            if (finalHitStation !== hoveredStation) { hoveredStation = finalHitStation; statusChanged = true; }

            if (statusChanged) {
                wrapper.style.cursor = (hoveredTrain || hoveredStation) ? 'pointer' : 'grab';
                if (typeof requestRedraw === 'function') requestRedraw();
                else redrawAll();
            }
        }
    });

    window.addEventListener('mouseup', (e) => {
        if (isDragging) {
            isDragging = false;
            wrapper.style.cursor = 'grab';
            let dist = Math.hypot(e.clientX - startMouseX, e.clientY - startMouseY);
            if (dist < 5) executeClick(e.clientX, e.clientY);
        }
    });

    wrapper.addEventListener('wheel', (e) => {
        e.preventDefault();
        const rect = wrapper.getBoundingClientRect();
        let zoom = e.deltaY > 0 ? 0.9 : 1.1;
        applyZoom(zoom, e.clientX - rect.left, e.clientY - rect.top);
    }, { passive: false });

    // ==========================================
    // 📱 [手機專區] 原生觸控事件 (Touch)
    // ==========================================
    let initialPinchDist = 0;
    let touchMoveDist = 0;
    let lastTouchX = 0, lastTouchY = 0;
    
    // 🌟 新增防護罩變數：記錄剛才是否在雙指縮放
    let wasPinching = false; 

    wrapper.addEventListener('touchstart', (e) => {
        e.preventDefault(); 
        if (e.touches.length === 1) {
            isDragging = true;
            touchMoveDist = 0;
            
            // 如果是真正的「全新單指落下」，解除防護罩
            if (e.touches.length === 1) wasPinching = false; 

            lastTouchX = e.touches[0].clientX;
            lastTouchY = e.touches[0].clientY;
            startMouseX = lastTouchX;
            startMouseY = lastTouchY;
            startCameraX = camera.x;
            startCameraY = camera.y;
        } else if (e.touches.length === 2) {
            isDragging = false;
            
            // 🌟 偵測到兩根手指，立刻開啟「絕對防點擊」防護罩！
            wasPinching = true; 
            
            initialPinchDist = Math.hypot(
                e.touches[0].clientX - e.touches[1].clientX,
                e.touches[0].clientY - e.touches[1].clientY
            );
        }
    }, { passive: false });

    wrapper.addEventListener('touchmove', (e) => {
        e.preventDefault();
        if (isDragging && e.touches.length === 1) {
            let dx = e.touches[0].clientX - startMouseX;
            let dy = e.touches[0].clientY - startMouseY;
            touchMoveDist += Math.abs(dx) + Math.abs(dy); 
            lastTouchX = e.touches[0].clientX;
            lastTouchY = e.touches[0].clientY;

            camera.x = startCameraX - dx;
            camera.y = startCameraY - dy;
            if (typeof clampCamera === 'function') clampCamera();
            if (typeof requestRedraw === 'function') requestRedraw();
            else redrawAll();

        } else if (e.touches.length === 2) {
            let currentDist = Math.hypot(
                e.touches[0].clientX - e.touches[1].clientX,
                e.touches[0].clientY - e.touches[1].clientY
            );
            if (initialPinchDist > 0) {
                let zoomDelta = currentDist / initialPinchDist;
                if (Math.abs(1 - zoomDelta) > 0.02) {
                    let midX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
                    let midY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
                    const rect = wrapper.getBoundingClientRect();
                    applyZoom(zoomDelta, midX - rect.left, midY - rect.top);
                    initialPinchDist = currentDist; 
                }
            }
        }
    }, { passive: false });

    wrapper.addEventListener('touchend', (e) => {
        e.preventDefault();
        if (e.touches.length === 0) { 
            if (isDragging) {
                isDragging = false;
                
                // 🌟 核心防呆：只有在「移動距離很小」且「剛剛沒有在縮放」時，才允許判定為點擊！
                if (touchMoveDist < 20 && !wasPinching) {
                    executeClick(lastTouchX, lastTouchY);
                }
            }
            initialPinchDist = 0;
            wasPinching = false; // 所有手指都離開了，重置防護罩
            
        } else if (e.touches.length === 1) { 
            isDragging = true;
            
            // 🌟 暴力破解法：如果從雙指變單指，強制把累積拖曳距離「灌滿到 999」，
            // 保證這根最後離開的手指，絕對不會被下一階段誤判成點擊！
            touchMoveDist = 999; 
            
            startMouseX = e.touches[0].clientX;
            startMouseY = e.touches[0].clientY;
            startCameraX = camera.x;
            startCameraY = camera.y;
        }
    }, { passive: false });

    // ==========================================
    // ⌨️ 全域鍵盤事件：按下 ESC 取消選取與解除過濾
    // ==========================================
    window.addEventListener('keydown', (e) => {
        // 檢查按下的鍵是不是 ESC
        if (e.key === 'Escape') {
            let needsRedraw = false;

            // 1. 清空火車與車站的選取狀態
            if (selectedTrain || selectedStation) {
                selectedTrain = null;
                selectedStation = null;
                if (typeof updateBottomPanel === 'function') updateBottomPanel(null);
                needsRedraw = true;
            }

            // 🌟 2. 升級：清空搜尋框！
            const searchInput = document.getElementById('search-input');
            const searchResults = document.getElementById('search-results');
            if (searchInput && searchInput.value !== '') {
                searchInput.value = '';
                if (searchResults) searchResults.style.display = 'none';
            }
            
            // 🌟 3. 升級：解除路線過濾模式！
            if (typeof activeRouteFilterTrains !== 'undefined' && activeRouteFilterTrains !== null) {
                activeRouteFilterTrains = null;
                needsRedraw = true;
            }

            // 如果有任何狀態改變，就重繪畫布
            if (needsRedraw) {
                if (typeof requestRedraw === 'function') requestRedraw();
                else if (typeof redrawAll === 'function') redrawAll();
            }
        }
    });
}

function requestRedraw() {
    if (!renderFrame) {
        renderFrame = requestAnimationFrame(() => {
            checkInfiniteScroll();
            redrawAll();
            renderFrame = null;
        });
    }
}

// ==========================================
// 將分鐘數轉換為 HH:MM 格式 (純淨版，支援負數校正)
// ==========================================
function formatTimeDisplay(minutesRaw) {
    if (minutesRaw === undefined || minutesRaw === null || minutesRaw === "") return "--:--";
    
    // 利用 ((x % 1440) + 1440) % 1440 讓負數時間也能完美回到 24 小時制的正確循環
    let wrappedMinutes = ((Math.floor(minutesRaw) % 1440) + 1440) % 1440; 
    
    let hours = Math.floor(wrappedMinutes / 60);
    let mins = wrappedMinutes % 60;
    
    let hStr = hours.toString().padStart(2, '0');
    let mStr = mins.toString().padStart(2, '0');
    
    // 直接回傳純時間，不加任何標籤
    return `${hStr}:${mStr}`; 
}

// ==========================================
// 🎨 色彩輔助：根據給定的數值調亮或調暗 Hex 色碼
// amount 為正數 (例如 50) 變淺/變亮，負數 (例如 -50) 變深/變暗
// ==========================================
function adjustBrightness(hex, amount) {
    // 防呆：如果是 undefined 或不是字串，直接回傳預設色
    if (!hex || typeof hex !== 'string') return '#FFFFFF';
    
    // 去掉 # 字號
    hex = hex.replace(/^#/, '');
    // 支援簡寫型色碼 (例如 #FFF 轉 #FFFFFF)
    if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');

    // 將 Hex 轉換為 10 進位的 R, G, B
    let r = parseInt(hex.substring(0, 2), 16);
    let g = parseInt(hex.substring(2, 4), 16);
    let b = parseInt(hex.substring(4, 6), 16);

    // 🌟 核心數學：加上你的「數字」，並限制在 0 ~ 255 之間
    r = Math.max(0, Math.min(255, r + amount));
    g = Math.max(0, Math.min(255, g + amount));
    b = Math.max(0, Math.min(255, b + amount));

    // 再轉回 16 進位字串並補零，最後加回 #
    return "#" + (1 << 24 | r << 16 | g << 8 | b).toString(16).slice(1).toUpperCase();
}

// ==========================================
// 🧮 數學輔助：計算「點」到「線段」的最短距離
// ==========================================
function getDistanceToSegment(px, py, x1, y1, x2, y2) {
    let l2 = (x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1);
    if (l2 === 0) return Math.sqrt((px - x1) * (px - x1) + (py - y1) * (py - y1));
    let t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2;
    t = Math.max(0, Math.min(1, t));
    let projX = x1 + t * (x2 - x1);
    let projY = y1 + t * (y2 - y1);
    return Math.sqrt((px - projX) * (px - projX) + (py - projY) * (py - projY));
}

// ==========================================
// 📖 專屬查字典工具：用 ID 去 segments 裡面挖出 st.name
// ==========================================
function getStationName(st_id) {
    if (!topology || !topology.segments) return st_id; 

    // 翻遍所有的路線段 (segments)
    for (let seg of topology.segments) {
        if (!seg.stations) continue;
        
        // 在這條路線的車站名單中，尋找 ID 相符的車站
        let foundStation = seg.stations.find(st => st.id === st_id);
        
        // 🌟 如果找到了，而且它有 name，就回傳中文站名！
        if (foundStation && foundStation.name) {
            return foundStation.name; 
        }
    }

    // 如果整本字典都翻遍了還是找不到，就退回原本的數字代碼
    return st_id;
}

// 判斷某個站 ID 是否存在於本系統拓樸中（僅 ID 查詢，不做名字比對）
function stationExistsInTopology(stId) {
    if (!topology || !topology.segments) return false;
    for (let seg of topology.segments) {
        if (!seg.stations) continue;
        if (seg.stations.some(st => st.id === stId)) return true;
    }
    return false;
}

// ==========================================
// 🌟 專為底部面板按鈕設計的「無縫切換函式」
// ==========================================
window.switchTrainKeepView = (trainNo) => {
    // 🌟 核心修復：交給正規引擎處理 BFS，且防止鏡頭跳動！
    window.triggerSelectTrain(trainNo, false, true);
};

// ==========================================
// 🎨 更新底部列車資訊面板 (對接現有的 bottom-bar)
// ==========================================
function updateBottomPanel(train) {
    const panel = document.getElementById('bottom-bar'); 
    if (!panel) return;

    // 如果沒有選中火車，恢復你原本寫的預設提示文字
    if (!train) {
        panel.innerHTML = `
            <div style="display: flex; align-items: center; width: 100%;">
                <h2 style="margin: 0 20px 0 0; font-size: 24px; color: var(--panel-text-main);">列車資訊</h2>
                <span style="font-size: 18px; color: var(--panel-text-sub);">點選列車或車站以顯示資訊</span>
            </div>
        `;
        // 🌟 核心修復：在 return 退出之前，強制拔除展開狀態，讓抽屜降下來！
        panel.classList.remove('expanded'); 
        return;
    }

    // 1. 取得車次與顏色
    let rawNo = train.no || train.train_no || train.id || "未知";
    let trainNo = String(rawNo).split('|')[0];
    let trainType = train.type || "";
    
    let trainColor = "#888888"; 
    let _typeColors = getTrainColorValue(trainType);
    if (_typeColors) {
        let typeColors = _typeColors;
        if (isDarkMode) {
            trainColor = typeColors[0]; 
        } else {
            // 🌟 一樣補上白字防呆機制
            let baseColor = typeColors[0].toUpperCase();
            trainColor = typeColors[1] || ((baseColor === '#FFFFFF' || baseColor === '#FFF' || baseColor === 'WHITE') ? '#222222' : typeColors[0]);
        }
    }

    // ==========================================
    // 🌟 核心升級：支援 show_train_type 與 show_train_id 自由開關
    // ==========================================
    let showType = !(settings && settings.show_train_type === false); // 預設 true
    let showId = !(settings && settings.show_train_id === false);     // 預設 true

    let displayTitle = "";
    if (showType && showId) {
        displayTitle = `${trainType} ${trainNo}`;
    } else if (showType && !showId) {
        displayTitle = `${trainType}`; // 👈 南海模式：只顯示「区間急行」
    } else if (!showType && showId) {
        displayTitle = `${trainNo}`;   // 只顯示車次
    } else {
        displayTitle = "列車";         // 兩個都關掉的保底防呆
    }

    // ==========================================
    // 🌟 新增：找出它的伴侶車，做成精美的快捷按鈕 (支援直通與併結)
    // ==========================================
    let partnerHtml = "";

    // 反向找「把 train 當 direct 後段」的前段車（single-direction coupling 補丁）
    const _findDirectPredecessor = (t) => {
        if (!t.segments || t.segments.length === 0) return null;
        let tNo = String(t.no || t.train_no || t.id);
        let tFirstSt = String(t.segments[0].s[0]);
        return timetable.find(pt => {
            if (!pt.coupled_with || !pt.segments || pt.segments.length === 0) return false;
            let ptLast = pt.segments[pt.segments.length - 1];
            if (String(ptLast.s[ptLast.s.length - 1]) !== tFirstSt) return false;
            return pt.coupled_with.some(c => c.action === "direct" && String(c.train_id) === tNo);
        });
    };

    const _pColor = (pTrain) => {
        let c = getTrainColorValue(pTrain.type);
        return c ? c[0] : "#888888";
    };

    if (train.coupled_with && train.coupled_with.length > 0) {
        train.coupled_with.forEach(c => {
            let pTrain = timetable.find(t => String(t.no || t.train_no || t.id) === String(c.train_id));
            if (pTrain) {
                let pColor = _pColor(pTrain);
                let cleanPno = String(pTrain.no).split('|')[0];
                if (c.action === "split" || c.action === "merge") {
                    partnerHtml += `
                        <span style="..." onclick="event.stopPropagation(); window.switchTrainKeepView('${pTrain.no}')">
                            🔗 併結 ${pTrain.type} ${cleanPno}
                        </span>
                    `;
                } else if (c.action === "direct") {
                    partnerHtml += `
                        <span style="..." onclick="event.stopPropagation(); window.switchTrainKeepView('${pTrain.no}')">
                            ➡️ 直通 ${pTrain.type} ${cleanPno}
                        </span>
                    `;
                }
            }
        });
    }
    // 單向 coupling：向前找前段車（如 普通 4140 找到 関空快速 4140M）
    const predTrain = _findDirectPredecessor(train);
    // 只要找到前段車，且 train 的 coupled_with 沒有反指回前段車（避免重複顯示），就加入
    const _predAlreadyShown = predTrain && train.coupled_with &&
        train.coupled_with.some(c => String(c.train_id) === String(predTrain.no || predTrain.train_no));
    if (predTrain && !_predAlreadyShown) {
        let cleanPno = String(predTrain.no).split('|')[0];
        // 前段車用 ⬅️ 表示「来自該車直通而來」
        let predBadge = `
            <span style="..." onclick="event.stopPropagation(); window.switchTrainKeepView('${predTrain.no}')">
                ⬅️ 前段 ${predTrain.type} ${cleanPno}
            </span>
        `;
        // 同時顯示前段車的 split 伴侶（如 紀州路快速）
        if (predTrain.coupled_with) {
            predTrain.coupled_with.forEach(c => {
                if (c.action !== "split") return;
                let sp = timetable.find(t => String(t.no || t.train_no || t.id) === String(c.train_id));
                if (sp) {
                    let spNo = String(sp.no).split('|')[0];
                    predBadge += `
                        <span style="..." onclick="event.stopPropagation(); window.switchTrainKeepView('${sp.no}')">
                            🔗 併結 ${sp.type} ${spNo}
                        </span>
                    `;
                }
            });
        }
        partnerHtml = predBadge + partnerHtml;
    }

    // ==========================================
    // 🌟 核心升級：建立「直通車次鏈」，自動向前後雙向串接並排序！
    // ==========================================
    let displayTrains = [];
    let visitedNos = new Set();
    let queue = [train]; // 從你點擊的這班車開始往外找

    // 1. 雙向抓取所有直通家族成員 (BFS 廣度優先搜尋)
    while (queue.length > 0) {
        let curr = queue.shift();
        let currId = String(curr.no || curr.train_no || curr.id);

        if (!visitedNos.has(currId)) {
            visitedNos.add(currId);
            displayTrains.push(curr);

            // Forward：curr.coupled_with → direct 後段
            if (curr.coupled_with) {
                curr.coupled_with.forEach(c => {
                    if (c.action === "direct") {
                        let partner = timetable.find(t => String(t.no || t.train_no || t.id) === String(c.train_id));
                        if (partner && !visitedNos.has(String(partner.no || partner.train_no || partner.id))) {
                            queue.push(partner);
                        }
                    }
                });
            }

            // Backward（single-direction coupling 補丁）：找「把 curr 當 direct 後段」的前段車
            const pred = _findDirectPredecessor(curr);
            if (pred && !visitedNos.has(String(pred.no || pred.train_no || pred.id))) {
                queue.push(pred);
            }
        }
    }

    

    // 2. 依據每台車第一站的「發車時間」由小到大排序 (確保物理順序正確)
    displayTrains.sort((a, b) => {
        let getStartTime = (tr) => {
            if (!tr.segments || tr.segments.length === 0) return 9999;
            // 抓這台車第一站的時間
            let firstTime = tr.segments[0].t[0] !== null ? tr.segments[0].t[0] : tr.segments[0].t[1];
            // 處理跨夜修正 (凌晨時段加 1440 確保它排在晚上後面)
            return (firstTime < 240) ? firstTime + 1440 : firstTime;
        };
        return getStartTime(a) - getStartTime(b);
    });

    // ==========================================
    // 同路線循環直通偵測（如大阪環状線每班接續的車）
    // 條件：直通鏈中有任一班車的起站 == 終站（環狀列車）
    // 這類不展開全鏈，改為只顯示本班停靠站 + 左右導覽按鈕
    // 跨路線直通（如 はるか 京都→関西空港）維持原本合併顯示
    // ==========================================
    const isSameRouteChain = displayTrains.length > 1 && displayTrains.some(t => {
        if (!t.segments || t.segments.length === 0) return false;
        const fSt = String(t.segments[0].s[0]);
        const lSeg = t.segments[t.segments.length - 1];
        return fSt === String(lSeg.s[lSeg.s.length - 1]);
    });

    let chainPrev = null, chainNext = null;
    if (isSameRouteChain) {
        const myIdx = displayTrains.findIndex(t => String(t.no) === String(train.no));
        chainPrev = myIdx > 0 ? displayTrains[myIdx - 1] : null;
        chainNext = myIdx < displayTrains.length - 1 ? displayTrains[myIdx + 1] : null;
        // 覆寫 partnerHtml：改為前後班次導覽按鈕
        const navStyle = `cursor:pointer; font-size:clamp(11px,2.5vw,14px); padding:3px 10px; border-radius:12px; background:rgba(255,255,255,0.12); display:inline-block; margin:0 4px; vertical-align:middle;`;
        partnerHtml = "";
        if (chainPrev) {
            const pNo = String(chainPrev.no).split('|')[0];
            partnerHtml += `<span style="${navStyle}" onclick="event.stopPropagation(); window.switchTrainKeepView('${chainPrev.no}')">← ${chainPrev.type} ${pNo}</span>`;
        }
        if (chainNext) {
            const nNo = String(chainNext.no).split('|')[0];
            partnerHtml += `<span style="${navStyle}" onclick="event.stopPropagation(); window.switchTrainKeepView('${chainNext.no}')">${chainNext.type} ${nNo} →</span>`;
        }
    }

    // 同路線鏈只渲染本班車；跨路線鏈保留完整鏈
    const effectiveDisplayTrains = isSameRouteChain ? [train] : displayTrains;

    // ==========================================
    // 🌟 自動抓取這班車 (含直通後) 的「絕對起點」與「絕對終點」
    // ==========================================
    let mainChainFirstSt = null;
    let mainChainLastSt = null;
    
    if (displayTrains.length > 0 && displayTrains[0].segments && displayTrains[0].segments.length > 0) {
        mainChainFirstSt = String(displayTrains[0].segments[0].s[0]);
        let lastTr = displayTrains[displayTrains.length - 1];
        if (lastTr.segments && lastTr.segments.length > 0) {
            let lastSeg = lastTr.segments[lastTr.segments.length - 1];
            mainChainLastSt = String(lastSeg.s[lastSeg.s.length - 1]);
        }
    }

    // ==========================================
    // 🌟 核心升級：解析併結路段 (自動補齊東京-盛岡等主幹線)
    // ==========================================
    let prefixStops = [];
    let suffixStops = [];

    // 直通鏈的「鏈頭車」與「鏈尾車」(可能不是使用者點擊的那台，例如點 395M 但鏈頭是 4631H)
    let _chainHead = displayTrains.length > 0 ? displayTrains[0] : train;
    let _chainTail = displayTrains.length > 0 ? displayTrains[displayTrains.length - 1] : train;

    // 👉 狀況 A (前段共用路段)：鏈頭車若在其「起站」從伴侶車 split/merge 出來，
    //    補上伴侶車交會點之前的共用停靠 (如紀州路快速 4631H 在日根野前與関空快速 4231M 併結 → 補京橋-日根野)
    if (_chainHead.coupled_with && mainChainFirstSt && mainChainLastSt) {
        let splitInfo = _chainHead.coupled_with.find(c => (c.action === "split" || c.action === "merge") && String(c.station_id) === mainChainFirstSt);
        if (splitInfo) {
            let partner = timetable.find(t => String(t.no || t.train_no || t.id) === String(splitInfo.train_id));
            let splitStId = String(splitInfo.station_id);
            if (partner) {
                // 併結母車本身可能還有直通前段（如 関空快速 4231M ← 普通 4231 天王寺-京橋），
                // 沿 direct 往回收集整條前段鏈，依發車時間排序後一路輸出到 split 點為止
                let prefChain = [];
                let seenPref = new Set();
                let qPref = [partner];
                while (qPref.length > 0) {
                    let cur = qPref.shift();
                    let curId = String(cur.no || cur.train_no || cur.id);
                    if (seenPref.has(curId)) continue;
                    seenPref.add(curId);
                    prefChain.push(cur);
                    let p = _findDirectPredecessor(cur);
                    if (p && !seenPref.has(String(p.no || p.train_no || p.id))) qPref.push(p);
                }
                prefChain.sort((a, b) => {
                    let st = tr => (tr.segments && tr.segments.length) ? (tr.segments[0].t[0] !== null ? tr.segments[0].t[0] : tr.segments[0].t[1]) : 9999;
                    let sa = st(a), sb = st(b);
                    return ((sa < 240 ? sa + 1440 : sa) - (sb < 240 ? sb + 1440 : sb));
                });
                let capturing = true;
                for (let tr of prefChain) {
                    for (let seg of tr.segments) {
                        for (let i = 0; i < seg.s.length; i++) {
                            let currId = String(seg.s[i]);
                            if (currId === splitStId) { capturing = false; break; }
                            if (capturing && seg.v[i] !== 2) {
                                prefixStops.push({
                                    id: seg.s[i], arr: seg.t[i*2], dep: seg.t[i*2+1],
                                    partnerNo: tr.no, partnerType: tr.type
                                });
                            }
                        }
                        if (!capturing) break;
                    }
                    if (!capturing) break;
                }
            }
        }
    }

    // 👉 狀況 B (後段共用路段)：鏈尾車若在其「終站」merge/split 進伴侶車，補上伴侶車交會點之後的共用停靠
    if (_chainTail.coupled_with && mainChainFirstSt && mainChainLastSt) {
        let splitInfo = _chainTail.coupled_with.find(c => (c.action === "split" || c.action === "merge") && String(c.station_id) === mainChainLastSt);
        if (splitInfo) {
            let partner = timetable.find(t => String(t.no || t.train_no || t.id) === String(splitInfo.train_id));
            let splitStId = String(splitInfo.station_id);
            if (partner) {
                let capturing = false;
                for (let seg of partner.segments) {
                    for (let i = 0; i < seg.s.length; i++) {
                        let currId = String(seg.s[i]);
                        // 跳過交會站本身，從下一站開始抓取
                        if (!capturing && currId === splitStId) { capturing = true; continue; }
                        if (capturing && seg.v[i] !== 2) {
                            suffixStops.push({
                                id: seg.s[i], arr: seg.t[i*2], dep: seg.t[i*2+1],
                                partnerNo: partner.no, partnerType: partner.type
                            });
                        }
                    }
                }
            }
        }
    }

    // ==========================================
    // 🌟 將所有停靠站平坦化為單一陣列，方便統一處理
    // ==========================================
    let allStops = [];
    
    // 1. 塞入前段併結路段 (如有)
    allStops.push(...prefixStops);

    // 2. 塞入原本這台車 (含直通) 的主路段
    effectiveDisplayTrains.forEach((tr, trIdx) => {
        if (tr.segments) {
            tr.segments.forEach((seg, segIdx) => {

                for (let i = 0; i < seg.s.length; i++) {
                    if (seg.v[i] === 2) continue; // 跳過通過站
                    
                    let arrRaw = seg.t[i * 2];
                    let depRaw = seg.t[i * 2 + 1];

                    // 直通時間修補 (維持原邏輯)
                    // ==========================================
                    // 🌟 修正：加入「交會站 ID 必須等於自己的終點站」的拓樸學驗證
                    // ==========================================
                    let lastSeg = tr.segments[tr.segments.length - 1];
                    let myLastSt = String(lastSeg.s[lastSeg.s.length - 1]);

                    let isDirectOut = (segIdx === tr.segments.length - 1 && i === seg.s.length - 1 &&
                        tr.coupled_with && tr.coupled_with.some(c => c.action === "direct" && String(c.station_id) === myLastSt &&
                            timetable.some(t => String(t.no || t.train_no || t.id) === String(c.train_id))));

                    if (isDirectOut) {
                        let dInfo = tr.coupled_with.find(c => c.action === "direct" && String(c.station_id) === myLastSt);
                        let nxt = timetable.find(tx => String(tx.no || tx.train_no || tx.id) === String(dInfo.train_id));
                        if (nxt && nxt.segments && nxt.segments.length > 0) {
                            depRaw = nxt.segments[0].t[1] !== undefined && nxt.segments[0].t[1] !== "" ? nxt.segments[0].t[1] : nxt.segments[0].t[0];
                        }
                    }

                    allStops.push({
                        id: seg.s[i],
                        arr: arrRaw,
                        dep: depRaw,
                        otherName: seg.is_other ? (seg.system_name || "其他系統") : null,  // 外運營商段（如 JR西日本）
                        otherPath: seg.is_other ? seg.system_path : null,
                        directStartNo: (trIdx > 0 && i === 0) ? tr.no : null // 標記直通起點
                    });
                }
            });
        }
    });

    // 3. 塞入後段併結路段 (如有)
    allStops.push(...suffixStops);

    // ==========================================
    // 🌟 動態更新標題的「絕對起點」與「絕對終點」
    // ==========================================
    let startStationName = "未知";
    let endStationName = "未知";
    // 🌟 略過 other_link 標記（它沒有 id），取真正的首/末停靠站，避免標題顯示 undefined
    let realStops = allStops.filter(s => s.type !== 'other_link');
    if (realStops.length > 0) {
        startStationName = getStationName(realStops[0].id);
        endStationName = getStationName(realStops[realStops.length - 1].id);
    }

    // ==========================================
    // 🌟 2. 組裝車站列表的 HTML (已移除小標籤純淨版)
    // ==========================================
    let stationsHtml = ``;
    let stopCount = 0; 
    let lastStationId = null;

    const _arrow = (color) => `<div class="station-arrow"${color ? ` style="color:${color};opacity:.6;"` : ''}>➔</div>`;
    const _stationCard = (stop) => `
            <div class="train-stop-item" onclick="window.triggerSelectStation('${stop.id}')">
                <div class="ts-col-name">${getStationName(stop.id)}</div>
                <div class="ts-col-arr">${formatTimeDisplay(stop.arr)}</div>
                <div class="ts-col-dep">${formatTimeDisplay(stop.dep)}</div>
            </div>`;
    const _otherStopCard = (stop) => {
        const stName = getStationName(stop.id);
        const inTopo = stationExistsInTopology(stop.id);
        return `<div class="train-stop-item${inTopo ? '' : ' other-op-stop'}"${inTopo ? ` onclick="window.triggerSelectStation('${stop.id}')"` : ''}>
                <div class="ts-col-name">${stName}</div>
                <div class="ts-col-arr">${formatTimeDisplay(stop.arr)}</div>
                <div class="ts-col-dep">${formatTimeDisplay(stop.dep)}</div>
            </div>`;
    };
    const OTHER_COLOR = "#3E8EDB"; // 外運營商（JR西日本）主色

    let si = 0;
    while (si < allStops.length) {
        let stop = allStops[si];

        // 防呆：交會站只印一次
        if (stop.id === lastStationId) { si++; continue; }

        // 外運營商段（如 JR西日本）：把連續同公司的站收進一個標註框
        if (stop.otherName) {
            let gName = stop.otherName, gPath = stop.otherPath, group = [];
            while (si < allStops.length && allStops[si].otherName === gName) {
                const s = allStops[si];
                if (s.id !== lastStationId) {
                    if (stationExistsInTopology(s.id)) {
                        // 本系統拓樸內的境界站（如 JR 上郡、阪急 天神橋筋六丁目）：
                        // 不加入藍框，也不更新 lastStationId，
                        // 讓後方的一般段正常渲染它。
                    } else {
                        group.push(s);
                        lastStationId = s.id;
                    }
                }
                si++;
            }
            if (group.length === 0) continue;
            if (stopCount > 0) stationsHtml += _arrow(OTHER_COLOR);
            let inner = group.map((s, i) => (i > 0 ? _arrow(OTHER_COLOR) : '') + _otherStopCard(s)).join('');
            let clickAttr = gPath ? `data-clickable="1" onclick="event.stopPropagation();window.switchToSystem('${gPath}')"` : '';
            let hint = gPath ? ` <span class="other-op-hint">↗&nbsp;運行圖</span>` : '';
            stationsHtml += `
                <div class="other-op-group">
                    <div class="other-op-label" ${clickAttr} title="點擊載入 ${gName} 運行圖">🚆 ${gName}${hint}</div>
                    ${inner}
                </div>`;
            stopCount += group.length;
            continue;
        }

        // 一般（本系統）停靠站
        lastStationId = stop.id;
        if (stopCount > 0) stationsHtml += _arrow();
        stationsHtml += _stationCard(stop);
        stopCount++;
        si++;
    }

    // 3. 塞進 bottom-bar（火車面板）
    // ── 家族全成員 chip row ──────────────────────────────────────────
    const _buildFamilyRow = () => {
        if (isSameRouteChain) return '';

        const getNo = t => String(t.no || t.train_no || t.id);
        const findT = id => timetable.find(t => getNo(t) === String(id));

        // ── 1. BFS：收集完整家族 ──
        const fam = new Map();
        const bfsQ = [...displayTrains];
        const pred0 = _findDirectPredecessor(train);
        if (pred0) bfsQ.push(pred0);
        while (bfsQ.length) {
            const t = bfsQ.shift();
            const no = getNo(t);
            if (fam.has(no)) continue;
            fam.set(no, t);
            (t.coupled_with || []).forEach(c => {
                if (c.action !== 'split' && c.action !== 'direct' && c.action !== 'merge') return;
                const nx = findT(c.train_id);
                if (nx && !fam.has(getNo(nx))) bfsQ.push(nx);
            });
            const p = _findDirectPredecessor(t);
            if (p && !fam.has(getNo(p))) bfsQ.push(p);
        }
        
        if (fam.size <= 1) return '';

        // ==========================================
        // 🌟 2. 物理時間尋根法 (徹底取代舊的 allTargets，無視指標混亂)
        // ==========================================
        let rootCandidates = [...fam.values()];

        rootCandidates.sort((a, b) => {
            const getStart = t => {
                if (!t.segments || !t.segments[0]) return 9999;
                let time = t.segments[0].t[0] !== null ? t.segments[0].t[0] : t.segments[0].t[1];
                return time < 240 ? time + 1440 : time;
            };
            
            let timeA = getStart(a);
            let timeB = getStart(b);

            // 💡 關鍵：如果發車時間一樣 (例如 20:44 東京發車的 159B 與 6159B)
            if (timeA === timeB) {
                // 誰身上帶有「正向指標 (爬蟲留下的)」，誰就優先當族譜源頭！
                let aHasForward = (a.coupled_with || []).some(c => !c._is_backward);
                let bHasForward = (b.coupled_with || []).some(c => !c._is_backward);
                
                if (aHasForward && !bHasForward) return -1;
                if (!aHasForward && bHasForward) return 1;

                return getNo(a).localeCompare(getNo(b)); 
            }
            
            return timeA - timeB; 
        });

        // 永遠選時間最前面的那台車當源頭
        const root = rootCandidates[0] || train;

        // ── 3. 遞迴建構拓樸樹 ──
        const buildNode = (t, vis) => {
            const no = getNo(t);
            if (vis.has(no)) return null; // 防無窮迴圈
            vis.add(no);
            
            const node = { train: t, next: null, splits: [], merges: [] };
            
            (t.coupled_with || []).forEach(c => {
                if (c._is_backward) return; // 🌟 嚴格遵守時間單向流動，不往回畫
                
                const partner = findT(c.train_id);
                if (!partner || vis.has(getNo(partner))) return;
                
                if (c.action === 'direct') {
                    node.next = buildNode(partner, vis);
                } else if (c.action === 'split') {
                    const child = buildNode(partner, new Set(vis));
                    if (child) node.splits.push(child);
                } else if (c.action === 'merge') {
                    const child = buildNode(partner, new Set(vis));
                    if (child) node.merges.push(child); 
                }
            });
            return node;
        };
        
        const tree = buildNode(root, new Set());
        if (!tree) return '';

        // ==========================================
        // 🌟 4. UI 膠囊產生器 (後面的程式碼維持不變...)
        // ==========================================

        // ==========================================
        // 🌟 4. UI 膠囊產生器
        // ==========================================
        const selectedNo = getNo(train);
        const mkChip = (t) => {
            let tNo = getNo(t);
            let isSelected = tNo === selectedNo;
            let tColor = _pColor(t);
            let cleanNo = tNo.split('|')[0];
            let label = (showType && showId) ? `${t.type} ${cleanNo}`
                      : showType ? (t.type || '')
                      : showId ? cleanNo
                      : '列車';
            
            if (isSelected) {
                return `<div style="display:inline-block; white-space:nowrap; font-size:clamp(20px, 5vw, 26px); font-weight:900; color:${tColor}; letter-spacing:1px; cursor:default; margin: 0 4px;">${label}</div>`;
            } else {
                return `<div style="display:inline-block; white-space:nowrap; font-size:18px; font-weight:700; color:${tColor}; cursor:pointer; opacity:0.85; transition:opacity 0.2s;" onclick="event.stopPropagation();window.switchTrainKeepView('${tNo}')" onmouseover="this.style.opacity='1'" onmouseout="this.style.opacity='0.85'">${label}</div>`;
            }
        };

        let lineColor = isDarkMode ? '#666' : '#CCC';

        // ── 5. CSS Flexbox 幾何對齊渲染引擎 (終極雙向 Grid 無縫對齊版) ──
        // ==========================================
        // 🌟 終極大一統：智慧型拓樸渲染引擎 (上行匯合支援 + 族譜診斷版)
        // ==========================================
        const renderNodeToHtml = (node) => {
            if (!node) return '';

            let chipHtml = mkChip(node.train);
            let lineColor = '#888'; 

            const getStartSta = (t) => {
                if (t?.data && t.data.length > 0) return t.data[0].sta || t.data[0].name;
                if (t?.stops && t.stops.length > 0) return t.stops[0].sta || t.stops[0].name;
                if (t?.segments && t.segments.length > 0) {
                    let firstSeg = t.segments[0];
                    if (firstSeg.s && firstSeg.s.length > 0) return firstSeg.s[0];
                    return firstSeg.source?.id || firstSeg.source?.sta || firstSeg.source?.name;
                }
                return "unknown_start_" + (t?.no || Math.random());
            };

            const getEndSta = (t) => {
                if (t?.data && t.data.length > 0) return t.data[t.data.length - 1].sta || t.data[t.data.length - 1].name;
                if (t?.stops && t.stops.length > 0) return t.stops[t.stops.length - 1].sta || t.stops[t.stops.length - 1].name;
                if (t?.segments && t.segments.length > 0) {
                    let lastSeg = t.segments[t.segments.length - 1];
                    if (lastSeg.s && lastSeg.s.length > 0) return lastSeg.s[lastSeg.s.length - 1];
                    return lastSeg.target?.id || lastSeg.target?.sta || lastSeg.target?.name;
                }
                return "unknown_end_" + (t?.no || Math.random());
            };

            // 定理 2-5：split / merge 對象一律視為平行，畫在左側
            // 優先使用 buildNode 已建好的樹節點（保留 .next 直通鏈），找不到才建最小節點
            const parallelPartners = (node.train.coupled_with || [])
                .filter(c => c.action === 'split' || c.action === 'merge')
                .map(c => {
                    const partner = findT(c.train_id);
                    if (!partner) return null;
                    const pNo = getNo(partner);
                    let nodeObj = node.merges.find(m => getNo(m.train) === pNo)
                                || node.splits.find(s => getNo(s.train) === pNo)
                                || { train: partner, next: null, splits: [], merges: [] };
                    
                    nodeObj.action = c.action; // 🌟 把 split 或 merge 的標記帶上
                    return nodeObj;
                })
                .filter(Boolean);

            let parallelGroup = [node, ...parallelPartners];

            // 🌟 核心修正 1：定義是否為合併群組 (此行保留原有的)
            const isMergeGroup = parallelGroup.some(p => p.action === 'merge');

            // merge 情境：找出所有平行成員共同匯入的後繼車 (此段保留原有的)
            const mergeNext = (() => {
                const hasMerge = (node.train.coupled_with || []).some(c => c.action === 'merge');
                if (!hasMerge) return null;
                if (node.next) return node.next;
                for (const pp of parallelPartners) { if (pp.next) return pp.next; }
                return null;
            })();

            // 🌟 核心修正 2：用 isMergeGroup 決定括弧位置，絕對不依賴 mergeNext 是否存在
            const hasLeftBracket = parallelGroup.length > 1 && !isMergeGroup;
            const hasRightBracket = parallelGroup.length > 1 && isMergeGroup;

            let gridRows = parallelGroup.map((pNode, idx) => {
                let isFirst = idx === 0;
                let isLast = idx === parallelGroup.length - 1;
                let pChipHtml = (pNode === node) ? chipHtml : mkChip(pNode.train);

                // 🌟 核心修正 3：分離左、右括弧的渲染邏輯，移除不必要的 transform
                let leftLineHtml = '';
                if (hasLeftBracket) {
                    leftLineHtml = `
                        <div style="position: relative; width: 10px; display: flex; align-items: center; align-self: stretch;">
                            <div style="width: 100%; height: 2px; background: ${lineColor};"></div>
                            <div style="position: absolute; left: 0; width: 2px; background: ${lineColor};
                                        top: ${isFirst ? 'calc(50% - 1px)' : '0'};
                                        bottom: ${isLast ? 'calc(50% - 1px)' : '0'};"></div>
                        </div>
                    `;
                }

                let rightLineHtml = '';
                if (hasRightBracket) {
                    rightLineHtml = `
                        <div style="position: relative; width: 10px; display: flex; align-items: center; align-self: stretch;">
                            <div style="width: 100%; height: 2px; background: ${lineColor};"></div>
                            <div style="position: absolute; right: 0; width: 2px; background: ${lineColor};
                                        top: ${isFirst ? 'calc(50% - 1px)' : '0'};
                                        bottom: ${isLast ? 'calc(50% - 1px)' : '0'};"></div>
                        </div>
                    `;
                }

                let futureBranches = [];
                // merge 後繼由外層統一渲染，不在各行個別顯示
                if (pNode.next && pNode.next !== mergeNext) futureBranches.push(pNode.next);
                
                if (pNode !== node && pNode.splits && pNode.splits.length > 0) {
                    let pNodeEnd = getEndSta(pNode.train);
                    pNode.splits.forEach(sNode => {
                        if (getStartSta(sNode.train) === pNodeEnd) futureBranches.push(sNode);
                    });
                }

                let extHtml = '';
                if (futureBranches.length === 1) {
                    extHtml = `
                        <div style="display:flex; align-items:center; height: 100%;">
                            <div style="width: 8px; height: 2px; background: ${lineColor}; flex-shrink: 0; margin: 0 4px;"></div>
                            ${renderNodeToHtml(futureBranches[0])}
                        </div>
                    `;
                } else if (futureBranches.length > 1) {
                    let branchesHtml = futureBranches.map((branch, bIdx) => {
                        let bFirst = bIdx === 0;
                        let bLast = bIdx === futureBranches.length - 1;
                        return `
                            <div style="display: flex; align-items: center; position: relative; padding: 2px 0;">
                                <div style="position: absolute; left: 0; width: 2px; background: ${lineColor};
                                            top: ${bFirst ? 'calc(50% - 1px)' : '0'};
                                            bottom: ${bLast ? 'calc(50% - 1px)' : '0'};"></div>
                                <div style="width: 8px; height: 2px; background: ${lineColor}; flex-shrink: 0;"></div>
                                <div style="margin-left: 4px;">
                                    ${renderNodeToHtml(branch)}
                                </div>
                            </div>
                        `;
                    }).join('');

                    extHtml = `
                        <div style="display:flex; align-items:center; height: 100%;">
                            <div style="width: 8px; height: 2px; background: ${lineColor}; flex-shrink: 0; margin-left: 4px;"></div>
                            <div style="display: flex; flex-direction: column;">
                                ${branchesHtml}
                            </div>
                        </div>
                    `;
                }

                const chipCol = hasLeftBracket ? '2' : '1';
                const rightBracketCol = hasLeftBracket ? '3' : '2';
                
                return `
                    <div style="display:contents;">
                        ${hasLeftBracket ? `<div style="grid-column: 1; align-self: stretch; display: flex;">${leftLineHtml}</div>` : ''}
                        <div style="grid-column: ${chipCol}; display:flex; align-items:center; padding: 2px 4px;">
                            ${pChipHtml}
                            ${extHtml}
                        </div>
                        ${hasRightBracket ? `<div style="grid-column: ${rightBracketCol}; align-self: stretch; display: flex;">${rightLineHtml}</div>` : ''}
                    </div>
                `;
            }).join('');

            // 🌟 核心修正 4：Grid 欄位定義也要嚴格依據 isMergeGroup
            let cols = parallelGroup.length > 1
                ? (isMergeGroup ? "max-content 10px" : "10px max-content")
                : "max-content";
                
            const gridHtml = `<div style="display: grid; grid-template-columns: ${cols}; align-items: center; gap: 0;">${gridRows}</div>`;
            
            if (mergeNext) {
                const sharedExtHtml = `<div style="display:flex; align-items:center;"><div style="width:8px; height:2px; background:${lineColor}; flex-shrink:0; margin:0 4px;"></div>${renderNodeToHtml(mergeNext)}</div>`;
                return `<div style="display:flex; align-items:center;">${gridHtml}${sharedExtHtml}</div>`;
            }
            return gridHtml;
        };

        return `<div style="display:flex; flex-direction:column; margin-bottom:12px; overflow-x:auto; padding-bottom:8px; align-items:flex-start;">${renderNodeToHtml(tree)}</div>`;
    };

        
    const familyRowHtml = _buildFamilyRow();
    const mainTitleHtml = familyRowHtml
        ? ''  // 有家族 row 時，主標題已包含在裡面
        : `<span style="font-size:clamp(20px,5vw,26px);font-weight:900;color:${trainColor};letter-spacing:1px;">${displayTitle}</span>`;

    panel.innerHTML = `
        <div class="bottom-panel-wrapper">
            <div class="train-info-header" onclick="document.getElementById('bottom-bar').classList.toggle('expanded')">
                <div style="line-height:1.3; display:flex; flex-direction:column;">
                    ${familyRowHtml || mainTitleHtml}
                    ${(!familyRowHtml && partnerHtml) ? `<div style="display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-top:4px;">${partnerHtml}</div>` : ''}
                </div>
                <div style="font-size: clamp(13px, 3.5vw, 16px); color: ${isDarkMode ? '#E0E0E0' : '#333333'}; opacity: 0.9; margin-top: 6px; font-weight: bold;">
                    ${startStationName} <span style="margin: 0 4px; opacity: 0.7; font-size: 0.8em;">▶</span> ${endStationName}
                </div>
                <div class="mobile-drag-handle"></div>
            </div>
            
            <!-- 🌟 終極防跑位：把標題放在外面 -->
            <div class="mobile-table-header" style="width: 100%; flex-shrink: 0;">
                <div style="flex: 1.5; text-align: left; padding-left: 10px;">站名</div>
                <div style="flex: 1; text-align: center;">到站時間</div>
                <div style="flex: 1; text-align: right; padding-right: 10px;">離站時間</div>
            </div>

            <div id="bottom-scroll-container">
                ${stationsHtml}
            </div>
        </div>
    `;
}

// ==========================================
// 🚉 更新底部面板 (拓樸學終點互鎖 + 智能同向合併版)
// ==========================================
function updateBottomPanelStation(st_id) {
    const panel = document.getElementById('bottom-bar'); 
    if (!panel) return;

    let stName = getStationName(st_id);
    let currentMinutes = getCurrentSystemMinutes();

    let upboundTrains = [];
    let downboundTrains = [];
    let processedTrains = new Set();

    // 🧠 核心升級：拓樸學終點追蹤器 (Data-Driven Topology Tracker)
    const getAbsoluteDest = (tObj) => {
        let curr = tObj;
        let visited = new Set([String(curr.no || curr.train_no || curr.id)]);
        
        while (true) {
            let advanced = false;
            
            let dInfo = curr.coupled_with ? curr.coupled_with.find(cx => cx.action === "direct") : null;
            if (dInfo) {
                let nxt = timetable.find(tx => String(tx.no || tx.train_no || tx.id) === String(dInfo.train_id));
                if (nxt && !visited.has(String(nxt.no || nxt.train_no || nxt.id))) {
                    visited.add(String(nxt.no || nxt.train_no || nxt.id));
                    curr = nxt;
                    advanced = true;
                }
            }
            if (advanced) continue;

            let splitInfo = curr.coupled_with ? curr.coupled_with.find(cx => cx.action === "split") : null;
            if (splitInfo) {
                let partner = timetable.find(tx => String(tx.no || tx.train_no || tx.id) === String(splitInfo.train_id));
                if (partner && !visited.has(String(partner.no || partner.train_no || partner.id))) {
                    
                    if (curr.segments && curr.segments.length > 0 && partner.segments && partner.segments.length > 0) {
                        let currLastSeg = curr.segments[curr.segments.length - 1];
                        let currLastStId = String(currLastSeg.s[currLastSeg.s.length - 1]);
                        
                        let partnerStations = partner.segments.flatMap(s => s.s).map(String);
                        let pIdx = partnerStations.indexOf(currLastStId);
                        
                        if (pIdx !== -1 && pIdx < partnerStations.length - 1) {
                            visited.add(String(partner.no || partner.train_no || partner.id));
                            curr = partner; 
                            advanced = true;
                        }
                    }
                }
            }
            if (advanced) continue;
            break; 
        }
        
        if (curr && curr.segments && curr.segments.length > 0) {
            let finalSeg = curr.segments[curr.segments.length - 1];
            return getStationName(finalSeg.s[finalSeg.s.length - 1]);
        }
        return "未知";
    };

    // 1. 尋找即將發車的班次
    timetable.forEach(train => {
        if (!activeTrainTypes.has(train.type) || !train.segments) return;

        let trainNo = train.no || train.train_no || "未知";
        if (processedTrains.has(trainNo)) return;

        for (let segIdx = 0; segIdx < train.segments.length; segIdx++) {
            if (processedTrains.has(trainNo)) break; 
            let seg = train.segments[segIdx];

            for (let i = 0; i < seg.s.length; i++) {
                if (seg.s[i] === st_id && seg.v[i] !== 2 && seg.v[i] !== 3) {
                    let depT = seg.t[i * 2 + 1];
                    let absoluteNow = currentMinutes < 120 ? currentMinutes + 1440 : currentMinutes;
                    let diff = depT - absoluteNow;
                    if (diff >= 0) {
                        let isUpbound = true;
                        let foundDirection = false;

                        // 以「同段、km 不同」的鄰站判斷上下行。參考站要跳過：
                        //   ① 交會站在段邊界的重複（與本站同 id）
                        //   ② is_other 外運營商站（不在拓樸、無 km）
                        // 優先用「之後」的鄰站；若之後全是外站（如神戸三宮之後的新開地方面），
                        // 改用「之前」的鄰站反推方向。否則會退回車號奇偶亂猜（hex stopCode 尤其失準）。
                        const _tryDir = (otherId, otherIsAfter) => {
                            if (!otherId || !topology || !topology.segments) return false;
                            for (let topoSeg of topology.segments) {
                                let a = topoSeg.stations.find(s => String(s.id) === String(st_id));
                                let b = topoSeg.stations.find(s => String(s.id) === String(otherId));
                                if (a && b && a.km !== undefined && b.km !== undefined && a.km !== b.km) {
                                    // 後站 km 較小 → 上行；前站 km 較大 → 上行
                                    isUpbound = otherIsAfter ? (b.km < a.km) : (a.km < b.km);
                                    return true;
                                }
                            }
                            return false;
                        };

                        // 往後走（跨段）找第一個能定向的拓樸內鄰站
                        for (let sj = segIdx; sj < train.segments.length && !foundDirection; sj++) {
                            let sseg = train.segments[sj];
                            let startK = (sj === segIdx) ? i + 1 : 0;
                            for (let k = startK; k < sseg.s.length; k++) {
                                if (String(sseg.s[k]) === String(st_id)) continue;
                                if (_tryDir(sseg.s[k], true)) { foundDirection = true; break; }
                            }
                        }
                        // 往後找不到（之後全為外站）→ 往前走反推
                        for (let sj = segIdx; sj >= 0 && !foundDirection; sj--) {
                            let sseg = train.segments[sj];
                            let endK = (sj === segIdx) ? i - 1 : sseg.s.length - 1;
                            for (let k = endK; k >= 0; k--) {
                                if (String(sseg.s[k]) === String(st_id)) continue;
                                if (_tryDir(sseg.s[k], false)) { foundDirection = true; break; }
                            }
                        }

                        if (!foundDirection) {
                            let match = String(trainNo).match(/\d+/g);
                            if (match) {
                                let lastNum = parseInt(match[match.length - 1], 10);
                                isUpbound = (lastNum % 2 === 0);
                            } else if (train.direction !== undefined) {
                                isUpbound = (train.direction === 0 || train.direction === "0");
                            } else {
                                isUpbound = true; 
                            }
                        }

                        let destName = getAbsoluteDest(train);

                        let trainData = {
                            train: train,
                            trainNo: trainNo,
                            depTime: depT,
                            destName: destName,
                            diff: diff
                        };

                        if (isUpbound) upboundTrains.push(trainData);
                        else downboundTrains.push(trainData);

                        processedTrains.add(trainNo);

                        // 輔助：判斷某車是否在本站有實際停靠（若有，主迴圈會自行加入，不需要在這裡補）
                        const _stopsAt = (t) => t.segments && t.segments.some(seg =>
                            seg.s.some((s, vi) => String(s) === String(st_id) && seg.v[vi] !== 2)
                        );

                        // 直通前段/後段（predecessor/successor）：
                        // 僅對「バス 代行」類型生效，避免環状線直通等場合誤加不相關班次
                        const _isBusRelated = (t) => t.type === "バス" ||
                            (t.coupled_with && t.coupled_with.some(c => c.action === "direct" && timetable.some(x =>
                                String(x.no || x.train_no || x.id) === String(c.train_id) && x.type === "バス"
                            )));

                        if (train.type === "バス") {
                            // 前段（バス が発見された時：前に走った普通車を表示）
                            let firstStId = String(train.segments[0].s[0]);
                            let predTrain = timetable.find(pt => {
                                if (!pt.coupled_with || !pt.segments || pt.segments.length === 0) return false;
                                let ptLastSeg = pt.segments[pt.segments.length - 1];
                                if (String(ptLastSeg.s[ptLastSeg.s.length - 1]) !== firstStId) return false;
                                return pt.coupled_with.some(c => c.action === "direct" && String(c.train_id) === String(train.no || train.train_no));
                            });
                            if (predTrain && !_stopsAt(predTrain)) {
                                let predNo = String(predTrain.no || predTrain.train_no || predTrain.id);
                                if (activeTrainTypes.has(predTrain.type) && !processedTrains.has(predNo)) {
                                    let pDestName = getAbsoluteDest(train);
                                    let pData = { train: predTrain, trainNo: predNo, depTime: depT, destName: pDestName, diff };
                                    if (isUpbound) upboundTrains.push(pData);
                                    else downboundTrains.push(pData);
                                    processedTrains.add(predNo);
                                }
                            }
                        }

                        // 直通後段（successor）＋ split 伴侶：需要 coupled_with 存在
                        if (train.coupled_with) {
                            // 直通後段：バス 類型才加「本身不停靠本站」的後段車
                            if (train.type === "バス") {
                            let lastSeg = train.segments[train.segments.length - 1];
                            let lastStId = String(lastSeg.s[lastSeg.s.length - 1]);
                            let succInfo = train.coupled_with.find(c => c.action === "direct" && String(c.station_id) === lastStId);
                            if (succInfo) {
                                let succTrain = timetable.find(t => String(t.no || t.train_no || t.id) === String(succInfo.train_id));
                                let succNo = succTrain && String(succTrain.no || succTrain.train_no || succTrain.id);
                                if (succTrain && !_stopsAt(succTrain) && activeTrainTypes.has(succTrain.type) && !processedTrains.has(succNo)) {
                                    let sDestName = getAbsoluteDest(succTrain);
                                    let sData = { train: succTrain, trainNo: succNo, depTime: depT, destName: sDestName, diff };
                                    if (isUpbound) upboundTrains.push(sData);
                                    else downboundTrains.push(sData);
                                    processedTrains.add(succNo);
                                }
                            }
                            }

                            train.coupled_with.forEach(c => {
                                if (c.action === "split") {
                                    let partner = timetable.find(t => String(t.no || t.train_no || t.id) === String(c.train_id));
                                    if (partner && !processedTrains.has(String(partner.no || partner.train_no || partner.id))) {
                                        
                                        let partnerHasStation = false;
                                        if (partner.segments) {
                                            for (let pSeg of partner.segments) {
                                                if (pSeg.s.map(String).includes(String(st_id))) {
                                                    partnerHasStation = true; break;
                                                }
                                            }
                                        }

                                        // 🌟 新增：地理拓樸共線判定
                                        let isSharedRoute = false;
                                        if (!partnerHasStation) {
                                            let hostStations = [];
                                            train.segments.forEach(seg => {
                                                hostStations.push(...seg.s.map(String));
                                            });
                                            
                                            // 找出當前車站與交會站(例如福島)在主車路線中的順序
                                            let currIdx = hostStations.indexOf(String(st_id));
                                            let splitIdx = hostStations.indexOf(String(c.station_id));
                                            
                                            if (currIdx !== -1 && splitIdx !== -1) {
                                                if (isUpbound) {
                                                    // 上行 (往東京)：交會站「之後」才開始共線 (例如福島之後的郡山、大宮)
                                                    isSharedRoute = (currIdx >= splitIdx);
                                                } else {
                                                    // 下行 (離開東京)：交會站「之前」才是共線 (例如東京到福島區間)
                                                    isSharedRoute = (currIdx <= splitIdx);
                                                }
                                            } else {
                                                // 防呆機制
                                                isSharedRoute = true; 
                                            }
                                        }

                                        // 只有確認在「共線區間」內，才幫伴侶車建立幽靈實體！
                                        if (!partnerHasStation && isSharedRoute) {
                                            let pDestName = getAbsoluteDest(partner);
                                            let pTrainNo = partner.no || partner.train_no || partner.id;

                                            let pTrainData = {
                                                train: partner,
                                                trainNo: String(pTrainNo),
                                                depTime: depT, 
                                                destName: pDestName,
                                                diff: diff
                                            };

                                            if (isUpbound) upboundTrains.push(pTrainData);
                                            else downboundTrains.push(pTrainData);

                                            processedTrains.add(String(pTrainNo));
                                        }
                                    }
                                }
                            });
                        }
                        break; 
                    }
                }
            }
        }
    });

    // 2. 依照發車時間排序
    upboundTrains.sort((a, b) => a.diff !== b.diff ? a.diff - b.diff : a.trainNo.localeCompare(b.trainNo));
    downboundTrains.sort((a, b) => a.diff !== b.diff ? a.diff - b.diff : a.trainNo.localeCompare(b.trainNo));

    // ==========================================
    // 🌟 終極魔法：智能同向合併 (Smart Merge + 物理併結驗證)
    // 必須符合：發車時間一樣 + 終點站一樣 + 具有實體 split 關聯
    // ==========================================
    const smartMerge = (trains) => {
        let res = [];
        let used = new Set();
        let showType = !(settings && settings.show_train_type === false);
        let showId = !(settings && settings.show_train_id === false);

        for (let i = 0; i < trains.length; i++) {
            if (used.has(i)) continue;
            let current = trains[i];
            let group = [current];

            for (let j = i + 1; j < trains.length; j++) {
                if (used.has(j)) continue;
                let other = trains[j];
                
                // 🛡️ 核心防護：檢查兩台車是否真的有「實體併結 (split)」關係
                let isPhysicallyCoupled = false;
                if (current.train.coupled_with) {
                    // 🌟 補上 merge
                    isPhysicallyCoupled = current.train.coupled_with.some(c => (c.action === "split" || c.action === "merge") && String(c.train_id) === String(other.trainNo));
                }
                if (!isPhysicallyCoupled && other.train.coupled_with) {
                    // 🌟 補上 merge
                    isPhysicallyCoupled = other.train.coupled_with.some(c => (c.action === "split" || c.action === "merge") && String(c.train_id) === String(current.trainNo));
                }
                
                // 條件嚴格：時間一致、終點一致，且「必須是物理上的併結車」才合併
                if (current.depTime === other.depTime && current.destName === other.destName && isPhysicallyCoupled) {
                    group.push(other);
                    used.add(j);
                }
            }

            if (group.length > 1) {
                let titles = group.map(g => {
                    if (showType && showId) return `${g.train.type} ${g.trainNo}`;
                    if (showType && !showId) return `${g.train.type}`;
                    if (!showType && showId) return `${g.trainNo}`;
                    return "列車";
                });
                
                res.push({
                    ...current,
                    displayTitleOverride: titles.join(" / ") // 產生合併字串
                });
            } else {
                res.push(current);
            }
        }
        return res;
    };

    upboundTrains = smartMerge(upboundTrains);
    downboundTrains = smartMerge(downboundTrains);

    // 3. UI 主題與骨架設定
    const theme = {
        cardBg: isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
        cardHoverBg: isDarkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.12)',
        textMain: isDarkMode ? '#FFFFFF' : '#222222',   
        textSub: isDarkMode ? '#AAAAAA' : '#666666',    
        border: isDarkMode ? '#444444' : '#DDDDDD',
        timeGray: isDarkMode ? '#BBBBBB' : '#666666' 
    };

    const buildRowHtml = (trains, dirLabel, dirColor) => {
        if (trains.length === 0) return `<div style="color: ${theme.textSub}; font-size: 13px; padding: 10px 20px; font-style: italic;">${dirLabel} 近期無班次</div>`;
        
        return trains.map(item => {
            let timeStr = formatTimeDisplay(item.depTime);
            
            let showType = !(settings && settings.show_train_type === false);
            let showId = !(settings && settings.show_train_id === false);
            
            // 1. 文字上色與開關邏輯
            const getTrainText = (trainObj, rawTrainNo) => {
                let colors = getTrainColorValue(trainObj.type);
                let tColor = colors ? (isDarkMode ? colors[0] : (colors[1] || colors[0])) : theme.textMain;
                

                let cleanTrainNo = String(rawTrainNo).split('|')[0];

                let parts = [];
                if (showType) {
                    parts.push(`<span style="color: ${tColor}; font-weight: bold; font-size: 14px;">${trainObj.type}</span>`);
                }
                if (showId) {
                    const idColor = showType ? theme.textMain : tColor;
                    const idMargin = showType ? ' margin-left: 4px;' : '';
                    parts.push(`<span style="color: ${idColor}; font-size: ${showType ? 13 : 14}px;${idMargin} font-weight: ${showType ? 'normal' : 'bold'};">${cleanTrainNo}</span>`);
                }
                
                if (parts.length === 0) {
                    return `<span style="color: ${tColor}; font-weight: bold; font-size: 14px;">列車</span>`;
                }
                
                return parts.join('');
            };

            // 2. 處理合併顯示
            let titleHtml = "";
            if (item.displayTitleOverride) {
                let group = item.train.coupled_with ? [item.train, ...item.train.coupled_with.filter(c => c.action === "split").map(c => timetable.find(t => String(t.no || t.train_no || t.id) === String(c.train_id)))] : [item.train];
                titleHtml = group.map(g => g ? getTrainText(g, g.no || g.train_no || g.id) : "").join(`<span style="color: ${theme.textSub}; margin: 0 4px;">/</span>`);
            } else {
                titleHtml = getTrainText(item.train, item.trainNo);
            }

            return `
                <div class="station-board-item" onclick="window.triggerSelectTrain('${item.trainNo}')" style="background: ${theme.cardBg}; border-bottom: 1px solid ${theme.border}; padding: 10px 16px; cursor: pointer;">
                    <div style="display: flex; align-items: center; gap: 12px; width: 100%;">
                        
                        <div style="display: flex; flex-direction: column; align-items: flex-start; width: 55px; flex-shrink: 0;">
                            <div style="font-size: 17px; color: ${theme.textMain};">
                                ${timeStr}
                            </div>
                            <div style="color: ${theme.textSub}; font-size: 11px; margin-top: 2px;">
                                ${Math.floor(item.diff)}分
                            </div>
                        </div>
                        
                        <div style="flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0;">
                            <div style="display: flex; align-items: baseline; flex-wrap: wrap;">
                                ${titleHtml}
                            </div>
                            <div style="font-size: 13px; color: ${theme.textMain}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                往 ${item.destName}
                            </div>
                        </div>

                    </div>
                </div>
            `;
        }).join('');
    };

    // 4. 組裝最終介面
    panel.innerHTML = `
        <div class="bottom-panel-wrapper">
            <div class="train-info-header" onclick="document.getElementById('bottom-bar').classList.toggle('expanded')">
                <div style="width: 100%; overflow-x: auto; white-space: nowrap; scrollbar-width: none; text-align: left;">
                    <div style="font-size: clamp(20px, 5vw, 26px); font-weight: 900; color: ${theme.textMain}; letter-spacing: 1px; display: inline-block;">${stName}</div>
                </div>
                <div style="font-size: clamp(13px, 3.5vw, 16px); color: ${theme.textSub}; margin-top: 4px; font-weight: bold;">即將發車</div>
                <div class="mobile-drag-handle"></div>
            </div>

            <div class="desktop-dir-col">
                <div style="color: var(--up-text); font-size: 13px; font-weight: bold; white-space: nowrap;">▲ 上行</div>
                <div style="color: var(--down-text); font-size: 13px; font-weight: bold; white-space: nowrap;">▼ 下行</div>
            </div>

            <div class="station-tab-bar" style="display: none;"> 
                <div class="station-tab active" id="tab-up" onclick="switchStationTab(0)">▲ 上行</div>
                <div class="station-tab" id="tab-down" onclick="switchStationTab(1)">▼ 下行</div>
            </div>

            <div class="mobile-table-header" style="width: 100%; flex-shrink: 0;">
                <div style="flex: 1.5; text-align: left; padding-left: 10px;">車次</div>
                <div style="flex: 1; text-align: center;">發車時間</div>
                <div style="flex: 1; text-align: right; padding-right: 10px;">目的地</div>
            </div>

            <div id="bottom-scroll-container" class="is-station">
                <div class="swipe-panel">
                    <div class="board-group" style="margin-top: 4px;">
                        ${buildRowHtml(upboundTrains, '▲ 上行', 'var(--up-badge-bg)')}
                    </div>
                </div>
                <div class="swipe-panel">
                    <div class="board-group">
                        ${buildRowHtml(downboundTrains, '▼ 下行', 'var(--down-badge-bg)')}
                    </div>
                </div>
            </div>
        </div>
    `;
}

// ==========================================
// 🌟 核心升級：通用折返路線拆解器 (Switchback Splitter)
// 專門解決前端內插法遇到「V字折返(如近鐵奈良)」會把折返點刪除的致命 Bug
// ==========================================
function splitSwitchbackSegments(trainsData, topology) {
    if (!topology || !topology.segments) return;

    trainsData.forEach(train => {
        if (!train.segments) return;
        let newSegments = [];

        train.segments.forEach(seg => {
            let topoSeg = topology.segments.find(t => String(t.id) === String(seg.id));
            // 如果找不到實體路線，或停靠站少於 3 個(不可能折返)，直接放行
            if (!topoSeg || seg.s.length < 3) {
                newSegments.push(seg);
                return;
            }

            // 1. 查出這條線所有停靠站在 topology 中的「絕對索引值」
            let indices = seg.s.map(st_id => topoSeg.stations.findIndex(t_st => String(t_st.id) === String(st_id)));

            let splitPoints = [];
            let currentDir = null; // 1 代表數值遞增(往東/南)，-1 代表遞減(往西/北)

            // 2. 掃描陣列，偵測「行駛方向」是否發生逆轉！
            for (let i = 0; i < indices.length - 1; i++) {
                let idx1 = indices[i];
                let idx2 = indices[i+1];
                if (idx1 === -1 || idx2 === -1) continue;

                let dir = idx2 > idx1 ? 1 : (idx2 < idx1 ? -1 : 0);
                if (dir !== 0) {
                    if (currentDir === null) {
                        currentDir = dir;
                    } else if (currentDir !== dir) {
                        // 💥 抓到了！方向逆轉了！把這個轉折點記下來！
                        splitPoints.push(i);
                        currentDir = dir;
                    }
                }
            }

            // 3. 根據轉折點，把這段路線狠狠劈成兩半 (或多半)
            if (splitPoints.length === 0) {
                newSegments.push(seg);
            } else {
                let startIndex = 0;
                for (let sp of splitPoints) {
                    newSegments.push({
                        id: seg.id,
                        s: seg.s.slice(startIndex, sp + 1),
                        t: seg.t.slice(startIndex * 2, (sp + 1) * 2),
                        v: seg.v.slice(startIndex, sp + 1)
                    });
                    startIndex = sp;
                }
                // 把最後剩下的尾巴也推入
                newSegments.push({
                    id: seg.id,
                    s: seg.s.slice(startIndex),
                    t: seg.t.slice(startIndex * 2),
                    v: seg.v.slice(startIndex)
                });
            }
        });
        
        // 用拆解完的安全路段覆蓋原本的資料
        train.segments = newSegments;
    });
}

// ==========================================
// 🌟 核心升級：時刻表自動補點 (空間線性內插法)
// 解決快車未紀錄通過站，導致畫布支線(如內灣線)斷線的問題
// ==========================================
function interpolatePassingStations(timetable, topology) {
    if (!topology || !topology.segments) return;

    timetable.forEach(train => {
        if (!train.segments) return;

        train.segments.forEach(seg => {
            // 1. 找出這條線在 topology 裡的實體鐵軌資料
            let topoSeg = topology.segments.find(t => String(t.id) === String(seg.id));
            if (!topoSeg || !topoSeg.stations) return;

            let new_s = [];
            let new_t = [];
            let new_v = [];

            // 2. 確定這班車在這段實體線的起點與終點
            let startIdx = topoSeg.stations.findIndex(st => String(st.id) === String(seg.s[0]));
            let endIdx = topoSeg.stations.findIndex(st => String(st.id) === String(seg.s[seg.s.length - 1]));

            if (startIdx === -1 || endIdx === -1) return; // 防呆機制

            let step = startIdx <= endIdx ? 1 : -1;
            let lastKnownIdx = 0; // 紀錄「上一個有在時刻表裡的站」

            // 3. 順著實體鐵軌一路往下走，檢查每個車站
            for (let i = startIdx; startIdx <= endIdx ? i <= endIdx : i >= endIdx; i += step) {
                let currentTopoSt = topoSeg.stations[i];
                let originalIdx = seg.s.findIndex(id => String(id) === String(currentTopoSt.id));

                if (originalIdx !== -1) {
                    // 👉 狀況 A：這個站原本就在時刻表裡 (有停靠、或原本就有抓到的通過站)
                    new_s.push(seg.s[originalIdx]);
                    new_t.push(seg.t[originalIdx * 2], seg.t[originalIdx * 2 + 1]);
                    new_v.push(seg.v[originalIdx]);
                    lastKnownIdx = originalIdx; // 更新進度
                } else {
                    // 👉 狀況 B：抓到漏網之魚！(例如北新竹)
                    let nextKnownIdx = lastKnownIdx + 1;

                    // 確保後面還有站可以對照
                    if (nextKnownIdx < seg.s.length) {
                        let prevStId = seg.s[lastKnownIdx];
                        let nextStId = seg.s[nextKnownIdx];

                        let prevTopoSt = topoSeg.stations.find(st => String(st.id) === String(prevStId));
                        let nextTopoSt = topoSeg.stations.find(st => String(st.id) === String(nextStId));

                        // 必須要有里程數才能計算比例
                        if (prevTopoSt && nextTopoSt && currentTopoSt.km !== undefined) {
                            let t1 = seg.t[lastKnownIdx * 2 + 1]; // 上一站離站時間
                            let t2 = seg.t[nextKnownIdx * 2];     // 下一站到站時間

                            // 處理跨夜邏輯 (例如 23:50 到 00:10)
                            if (t2 < t1) t2 += 1440;

                            // 🧮 依「里程比例」計算通過時間
                            let totalDist = Math.abs(nextTopoSt.km - prevTopoSt.km);
                            let currentDist = Math.abs(currentTopoSt.km - prevTopoSt.km);

                            let passTime = t1;
                            if (totalDist > 0) {
                                passTime = t1 + (t2 - t1) * (currentDist / totalDist);
                            }

                            // 將算出來的通過站偷偷塞進去
                            new_s.push(currentTopoSt.id);
                            new_t.push(passTime, passTime); // 通過站的到離時間一樣
                            new_v.push(2); // 2 代表「通過」
                        }
                    }
                }
            }

            // 4. 用補滿的資料覆蓋掉原本有破洞的資料
            seg.s = new_s;
            seg.t = new_t;
            seg.v = new_v;
        });
    });
}

// ==========================================
// 🌟 資料水合引擎：自動建立雙向併結/直通指標 (修復跨夜車覆蓋 Bug)
// ==========================================
function buildBidirectionalCoupling(timetableData) {
    if (!timetableData) return;

    timetableData.forEach(train => {
        if (!train.coupled_with) return;

        let myId = String(train.no || train.train_no || train.id);
        let currentCouples = [...train.coupled_with];

        currentCouples.forEach(c => {
            if (c.action === "direct_from" || c._is_backward) return;

            let partnerId = String(c.train_id);

            // 今天的車只配對今天的車，昨天的殘影只配對昨天的殘影
            let partners = timetableData.filter(t =>
                String(t.no || t.train_no || t.id) === partnerId &&
                !!t._isYesterday === !!train._isYesterday
            );

            let reverseAction = c.action === "direct" ? "direct_from" : c.action;

            partners.forEach(partner => {
                if (!partner.coupled_with) partner.coupled_with = [];

                let exists = partner.coupled_with.some(pc =>
                    String(pc.train_id) === myId && pc.action === reverseAction
                );

                if (!exists) {
                    partner.coupled_with.push({
                        train_id: myId,
                        action: reverseAction,
                        station_id: c.station_id,
                        _is_backward: true
                    });
                }
            });
        });
    });
}

// ==========================================
// 🌟 完美縫合器 (修復跨夜時光倒流 Bug)
// ==========================================
function stitchTrainSegments(trainsData, topology) {
    if (!topology || !topology.segments) return;

    const getStationKm = (stId, lineId) => {
        let seg = topology.segments.find(s => String(s.id) === String(lineId));
        if (seg) {
            let st = seg.stations.find(s => String(s.id) === String(stId));
            if (st && st.km !== undefined) return st.km;
        }
        return null;
    };

    trainsData.forEach(train => {
        if (!train.segments || train.segments.length < 2) return;

        // 🛑 核心修復：為自動造橋器加上「跨夜修正」，避免凌晨的區段被丟到最前面！
        train.segments.sort((a, b) => {
            let tA = (a.t && a.t[0] !== null && a.t[0] !== undefined) ? a.t[0] : 0;
            let tB = (b.t && b.t[0] !== null && b.t[0] !== undefined) ? b.t[0] : 0;
            
            let adjA = tA < 240 ? tA + 1440 : tA;
            let adjB = tB < 240 ? tB + 1440 : tB;
            
            return adjA - adjB;
        });

        for (let i = 0; i < train.segments.length - 1; i++) {
            let segA = train.segments[i];
            let segB = train.segments[i + 1];
            
            // ... (下面這段維持原本你貼入的邏輯不變) ...
            let lastStA = segA.s[segA.s.length - 1];
            let firstStB = segB.s[0];

            if (String(lastStA) !== String(firstStB)) {
                let junc = getJunction(lastStA, firstStB, segA.id, segB.id);
                // 👉 狀況 A：正常的直接交會
                if (junc && junc.type === 'direct') {
                    let juncId = junc.id;
                    let tA = segA.t[segA.t.length - 1]; 
                    let tB = segB.t[0];                 

                    let kmA = getStationKm(lastStA, segA.id);
                    let kmJ_A = getStationKm(juncId, segA.id);
                    let kmJ_B = getStationKm(juncId, segB.id);
                    let kmB = getStationKm(firstStB, segB.id);

                    if (kmA !== null && kmJ_A !== null && kmJ_B !== null && kmB !== null) {
                        let distA_J = Math.abs(kmJ_A - kmA);
                        let distJ_B = Math.abs(kmB - kmJ_B);
                        let totalDist = distA_J + distJ_B;

                        let passTime = tA;
                        if (totalDist > 0) {
                            let tB_adj = tB < tA ? tB + 1440 : tB; 
                            passTime = tA + (tB_adj - tA) * (distA_J / totalDist);
                            if (passTime >= 1440) passTime -= 1440;
                        }

                        // 防呆：避免塞入重複的站點
                        if (lastStA !== juncId) {
                            segA.s.push(juncId);
                            segA.t.push(passTime, passTime);
                            segA.v.push(2); 
                        }
                        if (firstStB !== juncId) {
                            segB.s.unshift(juncId);
                            segB.t.unshift(passTime, passTime);
                            segB.v.unshift(2); 
                        }
                    }
                } 
                // 👉 狀況 B：無中生有造橋！(解決名古屋線直通難波線的問題)
                else if (junc && junc.type === 'bridge') {
                    let junc1 = junc.junc1; // 伊勢中川
                    let junc2 = junc.junc2; // 鶴橋

                    let tA = segA.t[segA.t.length - 1];
                    let tB = segB.t[0];

                    let kmA = getStationKm(lastStA, segA.id);
                    let kmJ1_A = getStationKm(junc1, segA.id);
                    let kmJ1_Bridge = getStationKm(junc1, junc.line);
                    let kmJ2_Bridge = getStationKm(junc2, junc.line);
                    let kmJ2_B = getStationKm(junc2, segB.id);
                    let kmB = getStationKm(firstStB, segB.id);

                    if (kmA !== null && kmJ1_A !== null && kmJ1_Bridge !== null && kmJ2_Bridge !== null && kmJ2_B !== null && kmB !== null) {
                        let dist1 = Math.abs(kmJ1_A - kmA);
                        let distBridge = Math.abs(kmJ2_Bridge - kmJ1_Bridge);
                        let dist2 = Math.abs(kmB - kmJ2_B);
                        let totalDist = dist1 + distBridge + dist2;

                        if (totalDist > 0) {
                            let tB_adj = tB < tA ? tB + 1440 : tB;
                            let tJunc1 = tA + (tB_adj - tA) * (dist1 / totalDist);
                            let tJunc2 = tA + (tB_adj - tA) * ((dist1 + distBridge) / totalDist);

                            if (tJunc1 >= 1440) tJunc1 -= 1440;
                            if (tJunc2 >= 1440) tJunc2 -= 1440;

                            // 1. 補齊上一段
                            if (lastStA !== junc1) {
                                segA.s.push(junc1);
                                segA.t.push(tJunc1, tJunc1);
                                segA.v.push(2);
                            }

                            // 2. 創造橋接段 (大阪線: 伊勢中川 -> 鶴橋)
                            let newSeg = {
                                id: junc.line,
                                s: [junc1, junc2],
                                t: [tJunc1, tJunc1, tJunc2, tJunc2],
                                v: [2, 2]
                            };

                            // 3. 補齊下一段 (如果下一段已經是鶴橋開頭，就不重複塞)
                            if (firstStB !== junc2) {
                                segB.s.unshift(junc2);
                                segB.t.unshift(tJunc2, tJunc2);
                                segB.v.unshift(2);
                            }

                            train.segments.splice(i + 1, 0, newSeg);
                            i++; // 跳過剛造好的橋，避免無限迴圈
                        }
                    }
                }
            }
        }
    });
}

// ==========================================
// 🎨 視覺優化濾鏡與時間校正
// ==========================================
function optimizeTrainTimesForDisplay(trainsData) {
    trainsData.forEach(train => {
        if (!train.segments) return;
        
        train.segments.forEach(seg => {
            // 🌟 1. 跨夜防呆：確保時間絕對不會「倒流」
            let lastT = seg.t[0];
            for (let i = 1; i < seg.t.length; i++) {
                if (seg.t[i] < lastT && (lastT - seg.t[i]) > 300) { 
                    seg.t[i] += 1440; 
                }
                lastT = Math.max(lastT, seg.t[i]); 
            }

            // ==========================================
            // 🌟 2. 新增：防止 0 分鐘瞬移 (垂直線掉落)
            // ==========================================
            for (let i = 2; i < seg.t.length; i += 2) {
                let prevDep = seg.t[i - 1]; // 上一站發車時間
                let currArr = seg.t[i];     // 這站到達時間
                
                // 如果這站的到達時間 <= 上一站的發車時間 (行車時間為 0)
                if (currArr <= prevDep) {
                    // 強制給予 0.5 分鐘的物理行駛時間，產生合理的斜率
                    seg.t[i] = prevDep + 0.5; 
                    
                    // 如果到達時間被往後推，擠到了這站原本的發車時間，發車時間也要順延
                    if (seg.t[i + 1] < seg.t[i]) {
                        seg.t[i + 1] = seg.t[i];
                    }
                }
            }

            // 🌟 3. 撐開停靠站的水平線
            for (let i = 0; i < seg.t.length; i += 2) {
                if (seg.t[i] === seg.t[i + 1] && seg.v[i / 2] !== 2) {
                    
                    // 🌟 玩家神級發現：併結站特判！
                    // 如果這台車在這個站發生拆解/併結，絕對不加 0.5 offset！
                    // 否則會導致它跟伴侶車的出發時間錯開 0.5 分鐘，造成黃線無法完美重疊。
                    let isCouplingStation = false;
                    if (train.coupled_with) {
                        let stId = seg.s[i / 2];
                        isCouplingStation = train.coupled_with.some(c => (c.action === "split" || c.action === "merge") && String(c.station_id) === String(stId));
                    }
                    
                    if (!isCouplingStation) {
                        seg.t[i + 1] += 0.5; 
                    }
                }
            }
        });
    });
}

window.triggerSelectTrain = function(trainNo, saveHistory = true, preventCameraJump = false) {
    let targetTrain = timetable.find(t => (t.no === trainNo || t.train_no === trainNo));

    if (targetTrain) {
        let historyData = window.buildTrainHistoryData(targetTrain);
        window.updateSearchInputText(historyData.keyword);
        if (saveHistory) {
            SearchHistoryManager.add({ type: 'train', id: historyData.id, keyword: historyData.keyword, displayHtml: historyData.displayHtml });
        }

        let originStationId = selectedStation;

        selectedTrain = targetTrain;
        selectedStation = null;
        
        // ==========================================
        // 🌟 新增：只有在點擊時，才執行一次龐大的 BFS 家族擴散運算！
        // ==========================================
        cachedStationChainSet = null; // 清空車站快取
        cachedPartnerIds = new Set();
        let pQueue = [selectedTrain];
        const chainNos = new Set([String(selectedTrain.no || selectedTrain.train_no || selectedTrain.id)]);

        const _isCircularTrain = (t) => {
            if (!t.segments || t.segments.length === 0) return false;
            return String(t.segments[0].s[0]) === String(t.segments[t.segments.length - 1].s[t.segments[t.segments.length - 1].s.length - 1]);
        };

        // ==========================================
        // 🌟 更新：光速 O(1) 家族擴散 (完美支援雙向指標)
        // ==========================================
        while (pQueue.length > 0) {
            let curr = pQueue.shift();
            let currNo = String(curr.no || curr.train_no || curr.id);
            const isChainMember = chainNos.has(currNo);

            if (curr.coupled_with) {
                curr.coupled_with.forEach(c => {
                    let pId = String(c.train_id);
                    if (cachedPartnerIds.has(pId)) return;
                    
                    // 🌟 嚴格配對：今天找今天，昨天找昨天，絕對不會找錯車！
                    let pTrain = timetable.find(t => 
                        String(t.no || t.train_no || t.id) === pId && 
                        (t._isYesterday === curr._isYesterday) 
                    );

                    if (!pTrain || pTrain === selectedTrain) return;

                    if (c.action === "split" || c.action === "merge") {
                        cachedPartnerIds.add(pId);
                        pQueue.push(pTrain);
                    } else if (c.action === "direct") {
                        if (_isCircularTrain(curr) || _isCircularTrain(pTrain)) return;
                        if (isChainMember) chainNos.add(pId);
                        cachedPartnerIds.add(pId);
                        pQueue.push(pTrain);
                    } else if (c.action === "direct_from") { // 🌟 新增：立刻讀取剛剛建好的反向直通指標
                        if (_isCircularTrain(curr) || _isCircularTrain(pTrain)) return;
                        cachedPartnerIds.add(pId);
                        pQueue.push(pTrain);
                    }
                });
            }
        }

        updateBottomPanel(selectedTrain);

        // ... (後面維持你原本尋找 targetMinutes 的邏輯)

        // 🌟 3. 查出這班車在剛剛那個車站的「準確時間」
        let targetMinutes = null;
        if (originStationId && targetTrain.segments) {
            for (let seg of targetTrain.segments) {
                for (let i = 0; i < seg.s.length; i++) {
                    if (String(seg.s[i]) === String(originStationId)) {
                        let arrTime = seg.t[i * 2];
                        let depTime = seg.t[i * 2 + 1];
                        
                        // 雙重保險抓取時間
                        if (arrTime !== null && arrTime !== undefined && arrTime !== "" && !isNaN(arrTime) && arrTime >= 0) {
                            targetMinutes = Number(arrTime);
                        } else if (depTime !== null && depTime !== undefined && depTime !== "" && !isNaN(depTime) && depTime >= 0) {
                            targetMinutes = Number(depTime);
                        }
                        break;
                    }
                }
                if (targetMinutes !== null) break;
            }
        }

        // 🌟 4. 呼叫超級大腦進行精準雙軸降落！
        if (preventCameraJump) {
            // 如果是點擊畫布或面板切換，不要移動鏡頭，原地重繪就好！
            if (typeof redrawAll === 'function') redrawAll();
        } else if (originStationId && targetMinutes !== null) {
            // 如果我們知道你是從哪個車站點的，就精準降落在那個「交會點」
            let stName = getStationName(originStationId);
            focusStationOnCanvas(originStationId, stName, targetMinutes);
        } 
        // 🌟 5. 保底機制：如果找不到交會點，就直接飛到這班車的「發車起站」！
        else if (targetTrain.segments && targetTrain.segments.length > 0) {
            let firstSeg = targetTrain.segments[0];
            let firstStationId = firstSeg.s[0];
            let stName = getStationName(firstStationId);
            let firstTime = firstSeg.t[0] !== null ? firstSeg.t[0] : firstSeg.t[1];
            
            if (firstTime !== null && firstTime !== undefined) {
                focusStationOnCanvas(firstStationId, stName, Number(firstTime));
            } else {
                redrawAll();
            }
        } else {
            redrawAll();
        }
    }
};

// ==========================================
// 🔄 跨系統無縫切換器 (防呆與路徑檢查版)
// ==========================================
window.switchToSystem = async function(systemPath) {
    // 1. 喚醒 Loading
    const loader = document.getElementById('loading-overlay');
    loader.classList.remove('hidden');

    try {
        // 2. 核心邏輯：從 global.json 檢查該路徑對應的系統是否為 active
        const res = await fetch('data/global.json');
        const globalData = await res.json();
        
        // 將系統清單攤平為一個陣列，方便查找（相容扁平 systems 與分組 groups）
        const allSystems = globalData.countries.flatMap(flattenSystems);
        
        // 檢查目標路徑是否存在，且 is_active 為 true
        const target = allSystems.find(s => systemPath.includes(s.id));
        
        if (!target || !target.is_active) {
            alert("🚧 該路線的運行圖尚未建置完成，敬請期待！");
            loader.classList.add('hidden');
            return;
        }

        // 3. 檢查通過，繼續原本的流程
        const basePath = window.location.hostname === 'localhost' ? '' : '/TRA_Visualization';
        const fullPath = `${basePath}/${systemPath}`;

        const checkRes = await fetch(`${fullPath}json/setting.json?t=${Date.now()}`);
        if (!checkRes.ok) throw new Error("File not found");
        
        init(fullPath); 
    } catch (e) {
        loader.classList.add('hidden');
        alert("🚧 系統切換失敗，請確認該系統資料已部署至伺服器。");
        console.error("Switch failed:", e);
    }
};

// ==========================================
// 🔄 跨面板互動觸發器 (終極驗屍官追蹤版)
// ==========================================
window.triggerSelectStation = function(st_id) {
    selectedStation = st_id;
    updateBottomPanelStation(selectedStation); 
    let stName = getStationName(st_id);
    window.updateSearchInputText(stName); 
    
    // 🌟 寫入歷史紀錄
    SearchHistoryManager.add({ type: 'station', id: st_id, keyword: stName, displayHtml: `<span class="search-item-badge badge-station">車站</span> <span style="margin-left: 8px;">${stName}</span>` });

    let targetMinutes = null;

    if (selectedTrain && selectedTrain.segments) {
        for (let seg of selectedTrain.segments) {
            for (let i = 0; i < seg.s.length; i++) {
                if (String(seg.s[i]) === String(st_id)) {
                    let arrTime = seg.t[i * 2];
                    let depTime = seg.t[i * 2 + 1];
                    
                    
                    if (arrTime !== null && arrTime !== undefined && arrTime !== "" && !isNaN(arrTime) && arrTime >= 0) {
                        targetMinutes = Number(arrTime);
                    } else if (depTime !== null && depTime !== undefined && depTime !== "" && !isNaN(depTime) && depTime >= 0) {
                        targetMinutes = Number(depTime);
                    }
                    break;
                }
            }
            if (targetMinutes !== null) break;
        }
    }

    focusStationOnCanvas(st_id, stName, targetMinutes);
};

// ==========================================
// 🌟 載入時刻表 (完美融合雙軌策略 + 跨夜殘影合成技術)
// ==========================================
async function loadTimetableData(dateOrType) {
    try {
        let dirc_path = currentSystemPath + "json/"; 
        let todayFileUrl = '';
        let yestFileUrl = '';

        let targetDateStr = ""; 
        let targetYestStr = "";

        // ------------------------------------------
        // 0. 根據策略，決定「今天」與「昨天」的檔案路徑
        // ------------------------------------------
        if (settings.data_fetch_strategy === "SINGLE_FILE") {
            // 🚃 情境 4 (觀光單一班表，如嵐山小火車)：全年共用一份 timetable_all.json
            // 由 available_dates.json 限定可選營運日（公休日於月曆中反灰）。
            targetDateStr = dateOrType;
            todayFileUrl = `${dirc_path}timetable/timetable_all.json`;
            yestFileUrl = todayFileUrl; // 同一份；無跨夜車故殘影自然為空
        } else if (settings.data_fetch_strategy === "DAILY_FILE") {
            // 🚄 情境 2 (台鐵/高鐵)：每日獨立檔案
            targetDateStr = dateOrType;
            let formattedDate = dateOrType.replace(/-/g, '');
            todayFileUrl = `${dirc_path}timetable/timetable_${formattedDate}.json`;

            let yestObj = new Date(dateOrType);
            yestObj.setDate(yestObj.getDate() - 1); 
            targetYestStr = `${yestObj.getFullYear()}-${String(yestObj.getMonth() + 1).padStart(2, '0')}-${String(yestObj.getDate()).padStart(2, '0')}`;
            yestFileUrl = `${dirc_path}timetable/timetable_${targetYestStr.replace(/-/g, '')}.json`;
            
        } else if (settings.data_fetch_strategy === "WEEKEND_FILE") {
            // 情境 1 & 3 都是讀取平假日檔案，但來源參數不同
            
            let todayType = "";
            let yestType = "";

            if (settings.calendar_type === "WEEKDAY_BITMAP") {
                // 🚅 情境 3 (新幹線)：用日期推算平假日
                targetDateStr = dateOrType;
                let todayObj = new Date(dateOrType);
                let isTodayWeekend = (todayObj.getDay() === 0 || todayObj.getDay() === 6);
                todayType = isTodayWeekend ? 'holiday' : 'weekday';

                let yestObj = new Date(todayObj);
                yestObj.setDate(yestObj.getDate() - 1);
                targetYestStr = `${yestObj.getFullYear()}-${String(yestObj.getMonth() + 1).padStart(2, '0')}-${String(yestObj.getDate()).padStart(2, '0')}`;
                let isYestWeekend = (yestObj.getDay() === 0 || yestObj.getDay() === 6);
                yestType = isYestWeekend ? 'holiday' : 'weekday';

            } else {
                // 🚃 情境 1 (私鐵)：直接傳入 weekday 或 holiday
                todayType = dateOrType;
                yestType = dateOrType; // 私鐵殘影借用同一份推算
            }

            todayFileUrl = `${dirc_path}timetable/timetable_${todayType}.json`;
            yestFileUrl = `${dirc_path}timetable/timetable_${yestType}.json`;
        }

        // ------------------------------------------
        // 1. 載入「今天」的時刻表並進行過濾
        // ------------------------------------------
        const timeRes = await fetch(todayFileUrl + '?t=' + Date.now());
        if (!timeRes.ok) throw new Error(`找不到檔案: ${todayFileUrl}`);
        let todayData = await timeRes.json();

        // 🌟 核心過濾器：如果此系統有日曆且是新幹線模式 (情境 3)，過濾不開的車
        if (settings.data_fetch_strategy === "WEEKEND_FILE" && settings.calendar_type === "WEEKDAY_BITMAP") {
            todayData = todayData.filter(train => {
                if (train.operation === "irregular") {
                    return train.dates && Array.isArray(train.dates) && train.dates.includes(targetDateStr);
                }
                // バス全線代行などで特定日を除外
                if (train.exclude_dates && Array.isArray(train.exclude_dates) && train.exclude_dates.includes(targetDateStr)) {
                    return false;
                }
                // 有効期間（X月Y日まで／から運転）：選取日超出範圍則不顯示
                if (train.valid_from && targetDateStr < train.valid_from) return false;
                if (train.valid_until && targetDateStr > train.valid_until) return false;
                return true;
            });
        }

        // ... (執行拆解、縫合與時間優化)
        splitSwitchbackSegments(todayData, topology);
        stitchTrainSegments(todayData, topology);
        optimizeTrainTimesForDisplay(todayData);
        interpolatePassingStations(todayData, topology);

        // ------------------------------------------
        // 2. 載入「昨天」的時刻表 (捕捉跨夜車殘影)
        // ------------------------------------------
        let yesterdayData = [];
        try {
            const yestRes = await fetch(yestFileUrl + '?t=' + Date.now());
            if (yestRes.ok) {
                let rawYesterday = await yestRes.json();

                // 🌟 同理，昨天的跨夜車殘影也要用「昨天的日期」過濾！
                if (settings.data_fetch_strategy === "WEEKEND_FILE" && settings.calendar_type === "WEEKDAY_BITMAP") {
                    rawYesterday = rawYesterday.filter(train => {
                        if (train.operation === "irregular") {
                            return train.dates && Array.isArray(train.dates) && train.dates.includes(targetYestStr);
                        }
                        if (train.exclude_dates && Array.isArray(train.exclude_dates) && train.exclude_dates.includes(targetYestStr)) {
                            return false;
                        }
                        if (train.valid_from && targetYestStr < train.valid_from) return false;
                        if (train.valid_until && targetYestStr > train.valid_until) return false;
                        return true;
                    });
                }
                
                // ... (保留你原本後續 rawYesterday 的縫合、推移 -1440 邏輯) ...
                stitchTrainSegments(rawYesterday, topology);
                optimizeTrainTimesForDisplay(rawYesterday);
                interpolatePassingStations(rawYesterday, topology);

                // 開始篩選並平移昨天的跨夜車
                rawYesterday.forEach(train => {
                    let hasCrossNight = false;
                    
                    // 為了不污染原始資料，做深拷貝
                    let shiftedTrain = JSON.parse(JSON.stringify(train));
                    shiftedTrain._isYesterday = true; // 做個記號，代表這是殘影車
                    
                    shiftedTrain.segments.forEach(seg => {
                        // 如果這條線有 >= 1440 的時間，代表它有跨到「今天」
                        if (seg.t.some(time => time >= 1440)) {
                            hasCrossNight = true;
                        }
                        // 🌟 核心魔法：將所有時間往前推一天 (-24小時)
                        seg.t = seg.t.map(time => time - 1440);
                    });

                    // 只有真正跨越午夜的車，才獲准加入今天的畫布
                    if (hasCrossNight) {
                        yesterdayData.push(shiftedTrain);
                    }
                });
            }
        } catch (e) {
            }

        // ------------------------------------------
        // 3. 雙劍合璧：將今天與昨天的跨夜殘影合併
        // ------------------------------------------
        timetable = todayData.concat(yesterdayData);
        currentDate = dateOrType; 

        buildBidirectionalCoupling(timetable);

        // 🌟 啟動權重計算機！根據這份剛合併好的班表，統計出今天的大站
        calculateStationWeights();

        // 大掃除
        selectedTrain = null;
        selectedStation = null;
        hoveredTrain = null;
        hoveredStation = null;
        updateBottomPanel(null);

        // 🌟 破案關鍵：切換平假日後，必須重新掃描新班表，生出專屬的車種按鈕！
        buildUI();
        updateTrainTypeVisibility();

        // 重新繪製新的一天的畫布
        redrawAll();

    } catch (e) {
        alert(`無法載入時刻表 (${dateOrType})！\n可能是資料尚未爬取。`);
        console.error(e);
    }
}

// 攤平一個國家的所有系統（相容扁平 country.systems 與分組 country.groups）
function flattenSystems(country) {
    if (Array.isArray(country.systems)) return country.systems;
    if (Array.isArray(country.groups)) return country.groups.flatMap(g => g.systems || []);
    return [];
}

// ==========================================
// 🌟 產生首頁系統選單
// ==========================================
async function loadSystemMenu() {
    try {
        // 🌟 核心新增：強制程式在這裡等，直到 GlowSans 等所有字體載入完畢！
        await document.fonts.ready;

        const res = await fetch('data/global.json');
        const globalData = await res.json();
        const container = document.getElementById('system-menu-container');

        // 字體等完了，資料也抓完了，這時才隱藏 Loading，顯示完美的字體首頁！
        document.getElementById('loading-overlay').classList.add('hidden');

        // 單一系統按鈕（country.id 決定資料路徑；分組僅為顯示用，不影響路徑）
        const makeSystemBtn = (countryId, sys) => {
            const btn = document.createElement('button');
            btn.className = 'pill-btn';
            btn.id = `btn-${sys.id}`;   // 身分證 ID，供 document 監聽器抓取
            if (sys.is_active) {
                btn.innerText = sys.chinese_name;
                btn.onclick = () => {
                    const dynamicPath = `data/${countryId}/${sys.id}/`;
                    const loader = document.getElementById('loading-overlay');
                    if (loader) {
                        loader.style.display = 'flex';
                        loader.classList.remove('hidden');
                    }
                    document.getElementById('landing-page').style.display = 'none';
                    document.getElementById('app').style.display = 'flex';
                    init(dynamicPath);
                };
            } else {
                btn.innerText = sys.chinese_name + " (建置中)";
                btn.style.opacity = "0.4";
                btn.style.cursor = "not-allowed";
            }
            container.appendChild(btn);
        };

        const groupTitle = (text) => {
            const el = document.createElement('div');
            el.style.cssText = "width: 100%; color: #BBBBBB; font-size: 14px; margin-top: 12px; margin-bottom: 6px; padding-left: 6px;";
            el.innerText = `— ${text} —`;
            container.appendChild(el);
        };

        globalData.countries.forEach(country => {
            // 建立國家標題
            const countryTitle = document.createElement('div');
            countryTitle.style.cssText = "width: 100%; color: #FFA500; font-size: 18px; margin-top: 20px; margin-bottom: 10px;";
            countryTitle.innerText = `📍 ${country.chinese_name}`;
            container.appendChild(countryTitle);

            // 分組（如日本：新幹線 / 關西）→ 每組一個小標題；無分組則直接列系統
            if (Array.isArray(country.groups)) {
                country.groups.forEach(group => {
                    groupTitle(group.chinese_name);
                    (group.systems || []).forEach(sys => makeSystemBtn(country.id, sys));
                });
            } else {
                (country.systems || []).forEach(sys => makeSystemBtn(country.id, sys));
            }
        });
    } catch (e) {
        console.error("無法載入系統清單", e);
    }
}

// ==========================================
// 🌟 綁定「回到首頁」按鈕 (終極重置版)
// ==========================================
function bindHomeButton() {
    const btnHome = document.getElementById('btn-home');

    if (!btnHome || isHomeBound) return; // 如果綁過就直接退場
    isHomeBound = true;
    
    if (btnHome) {
        btnHome.addEventListener('click', () => {
            // 1. 停止背景的重繪計時器
            if (renderIntervalId) {
                clearInterval(renderIntervalId);
                renderIntervalId = null;
            }

            // 2. 清空畫布
            const canvas = document.getElementById('diaCanvas');
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // 🌟 3. 核心修復：回到首頁時，強制清空所有選取狀態與抽屜！
            selectedTrain = null;
            selectedStation = null;
            const panel = document.getElementById('bottom-bar');
            if (panel) {
                panel.classList.remove('expanded'); // 強制收合抽屜
                if (typeof updateBottomPanel === 'function') updateBottomPanel(null); // 還原文字
            }

            // 清空搜尋框
            const searchInput = document.getElementById('search-input');
            const searchResults = document.getElementById('search-results');
            if (searchInput) searchInput.value = '';
            if (searchResults) searchResults.style.display = 'none';

            // 4. 轉場動畫：隱藏主畫面，顯示首頁選單
            document.getElementById('app').style.display = 'none';
            document.getElementById('landing-page').style.display = 'block'; 
        });
    }
}

// ==========================================
// 🌟 高畫質 Canvas 初始化工具 (解決模糊問題)
// ==========================================
function initCanvas(canvasId, wrapperId) {
    const canvas = document.getElementById(canvasId);
    const wrapper = document.getElementById(wrapperId);
    const ctx = canvas.getContext('2d');

    const dpr = window.devicePixelRatio || 1;

    // 🌟 加上 Math.round，確保不會產生小數點像素造成的邊緣模糊
    const displayWidth = Math.round(wrapper.clientWidth);
    const displayHeight = Math.round(wrapper.clientHeight);

    canvas.width = displayWidth * dpr;
    canvas.height = displayHeight * dpr;
    canvas.style.width = displayWidth + 'px';
    canvas.style.height = displayHeight + 'px';

    ctx.scale(dpr, dpr);

    return { canvas, ctx };
}

// ==========================================
// 🌟 動態過濾車種按鈕顯示 (嚴格檢驗停靠版)
// 確保只停 1 站的轉乘車 (空港急行) 會顯示，但通過不停的車 (ラピート) 會隱藏
// ==========================================
function updateTrainTypeVisibility() {
    if (!settings || !settings.view_presets || !currentRouteView) return;

    let selectedSegments = settings.view_presets[currentRouteView].lines || [];
    
    // 1. 取得當前視角「真正有畫出來的」所有車站 ID
    let segmentsData = getProcessedSegments(selectedSegments, topology);
    let activeStationIds = new Set();
    
    segmentsData.forEach(data => {
        data.stations.forEach(st => {
            activeStationIds.add(String(st.id));
        });
    });

    // 2. 找出「目前畫布上」真正有交集的車種清單
    let visibleTypes = new Set();
    
    timetable.forEach(train => {
        if (!train.segments) return;
        
        let hasValidStop = false;
        
        // 嚴格檢查這班車的每一個停靠紀錄
        for (let seg of train.segments) {
            for (let i = 0; i < seg.s.length; i++) {
                let st_id = String(seg.s[i]);
                let v_status = seg.v[i]; // 取出這個站的停靠狀態
                
                // 🌟 核心升級：必須踩在畫布的車站上，而且「絕對不能是通過站 (v !== 2)」！
                if (activeStationIds.has(st_id) && v_status !== 2) {
                    hasValidStop = true;
                    break; 
                }
            }
            if (hasValidStop) break;
        }
        
        // 只要有任何一個「實質停靠」，就放行！
        if (hasValidStop) {
            visibleTypes.add(train.type);
        }
    });

    // 3. 掃描右側面板的所有車種按鈕，控制顯示或隱藏
    let typeButtons = document.querySelectorAll('#train-type-container .pill-btn');

    typeButtons.forEach(btn => {
        let typeName = btn.innerText.trim();

        // 防呆：全選 / 全部不選 的按鈕絕對不能被隱藏
        if (btn.id === 'btn-all-trains' || btn.id === 'btn-no-trains') return;

        if (visibleTypes.has(typeName)) {
            btn.style.display = 'inline-block';
        } else {
            btn.style.display = 'none';
        }
    });

    // 4. 群組容器：若群組內所有 pill-btn 都被隱藏，整個群組也隱藏
    document.querySelectorAll('#train-type-container .train-type-group').forEach(groupDiv => {
        const haVisible = Array.from(groupDiv.querySelectorAll('.pill-btn'))
            .some(b => b.style.display !== 'none');
        groupDiv.style.display = haVisible ? '' : 'none';
    });
}

// ==========================================
// 📱 點擊頁籤時，控制面板左右滑動
// ==========================================
window.switchStationTab = function(index) {
    const scrollContainer = document.getElementById('bottom-scroll-container');
    if (scrollContainer) {
        const width = scrollContainer.clientWidth;
        scrollContainer.scrollTo({ left: index * width, behavior: 'smooth' });
    }
};

// ==========================================
// 📱 監聽使用者的「手指左右滑動」，動態更新頁籤的底線！
// ==========================================
document.addEventListener('scroll', function(e) {
    if (e.target.id === 'bottom-scroll-container' && e.target.classList.contains('is-station')) {
        const tabUp = document.getElementById('tab-up');
        const tabDown = document.getElementById('tab-down');
        
        if (tabUp && tabDown && window.innerWidth <= 768) {
            // 如果滾動超過一半，就判定切換到下一頁
            const scrollLeft = e.target.scrollLeft;
            const halfWidth = e.target.clientWidth / 2;
            
            if (scrollLeft > halfWidth) {
                tabUp.classList.remove('active');
                tabDown.classList.add('active');
            } else {
                tabUp.classList.add('active');
                tabDown.classList.remove('active');
            }
        }
    }
}, true); // 使用 Capture 模式確保能捕捉到內部 div 的 scroll 事件

// ==========================================
// 系統啟動點 (init)
// ==========================================
async function init(systemPath) {
    // 🌟 核心修正 1：日誌必須放在最頂端，確保我們知道 init 真的有動！
    
    // 🌟 修正：改用 ID 抓取，確保不受 Flatpickr 屬性變更影響
    const dateInput = document.getElementById('datePicker'); 
    if (dateInput) {
        dateInput.value = ""; 
        if (dateInput._flatpickr) {
            dateInput._flatpickr.destroy();
        }
    }
    
    // ==========================================
    // 🌟 切換系統大掃除：徹底抹除上一套系統的殘留影蹤
    // ==========================================
    if (typeof timetable !== 'undefined' && timetable.length > 0) {
        timetable.forEach(train => {
            if (train._hitPoints) train._hitPoints.length = 0; // 徹底清空舊系統的物理點
        });
    }
    
    // 重置選取狀態，避免舊系統的車站 ID 影響新系統
    selectedTrain = null;
    selectedStation = null;
    hoveredTrain = null;
    hoveredStation = null;
    
    // 清空時刻表與快取，確保重新開始
    timetable = [];
    junctionCache = {}; 
    // ==========================================

    // ==========================================
    // 🌟 新增：跨系統搜尋大掃除！
    // 確保切換系統時，自動解除路線過濾模式並清空搜尋框
    // ==========================================
    if (typeof activeRouteFilterTrains !== 'undefined') {
        activeRouteFilterTrains = null; // 解除畫布過濾
    }

    // 🌟 核心新增：徹底消滅上一個系統的歷史紀錄
    if (typeof SearchHistoryManager !== 'undefined') {
        SearchHistoryManager.clear();
    }

    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');
    if (searchInput) searchInput.value = '';             // 清空輸入框字體
    if (searchResults) searchResults.style.display = 'none'; // 收起下拉選單
    // ==========================================

    currentSystemPath = systemPath;

    try {
        
        let dirc_path = currentSystemPath + "json/"; // 確保路徑正確
        
        // 🌟 核心修正 2：所有的 fetch 都要加上 Cache Buster (?t=...)
        // 防止瀏覽器在切換系統時把「台鐵的檔案」當成「高鐵的檔案」餵給你
        const setRes = await fetch(`${dirc_path}setting.json?t=${Date.now()}`);
        if (!setRes.ok) throw new Error("找不到 setting.json");
        
        const settingText = await setRes.text();
        settings = JSON.parse(settingText);


        // 偵測 train_color 是否為巢狀分組格式，並建立 _rawOrder（葉節點型別順序）
        if (settings.train_color) {
            const firstVal = Object.values(settings.train_color)[0];
            const isGrouped = firstVal && typeof firstVal === 'object' && !Array.isArray(firstVal);
            settings._trainColorGrouped = isGrouped;
            if (isGrouped) {
                // 巢狀格式：從各分組依序收集葉節點車種名稱
                settings._rawOrder = Object.values(settings.train_color).flatMap(g => Object.keys(g));
            } else {
                // 舊格式：用 Object.keys 取得順序
                settings._rawOrder = Object.keys(settings.train_color);
            }
        }

        if (settings.system_name) {
            document.title = settings.system_name + " - 運行圖";
        }

        // 2. 載入 topology.json
        const topoRes = await fetch(dirc_path + 'topology.json?t=' + Date.now());
        topology = await topoRes.json();

        // ==========================================
        // 🌟 核心新增：單一線路防呆機制 (針對高鐵等沒有 view_presets 的系統)
        // ==========================================
        if (!settings.view_presets || Object.keys(settings.view_presets).length === 0) {
            // 如果 JSON 沒寫，我們就自己創造一個預設視角
            settings.view_presets = {
                "default_view": {
                    "name": "全線",
                    // 直接去 topology 裡面把所有的實體路線 ID 都抓進來串接
                    "lines": topology.segments.map(seg => seg.id), 
                    "view_type": "LINEAR"
                }
            };
        }

        // ==========================================
        // 🌟 3. 判斷 UI 呈現與預設日期載入策略
        // ==========================================
        const dateInput = document.getElementById('datePicker');
        let btnContainer = document.getElementById('weekendSelectContainer');

        if (settings.calendar_type === "WEEKDAY_BITMAP") {
            // 📅 情境 2 & 3 (台鐵、高鐵、新幹線)：使用月曆 UI
            
            // 隱藏平假日按鈕 (如果有的話)
            if (btnContainer) btnContainer.style.display = 'none';
            
            // 顯示並初始化月曆
            if (dateInput) {
                dateInput.style.display = '';
                dateInput.value = ""; 
                if (dateInput._flatpickr) dateInput._flatpickr.destroy();

                // 1. 先取得今天的實體日期作為預設值 (新幹線預設用這個)
                let todayObj = new Date();
                let todayStr = `${todayObj.getFullYear()}-${String(todayObj.getMonth() + 1).padStart(2, '0')}-${String(todayObj.getDate()).padStart(2, '0')}`;
                currentDate = todayStr;

                // 2. 準備 Flatpickr 的基礎設定檔 (先不要放入 enable 屬性)
                let flatpickrConfig = {
                    defaultDate: currentDate, 
                    dateFormat: "Y-m-d",
                    disableMobile: "true",
                    onChange: async function(selectedDates, dateStr, instance) {
                        await loadTimetableData(dateStr);
                    }
                };

                // 🌟 3. 「每日獨立檔案 (台鐵/高鐵)」與「單一班表 (觀光線)」都需要可選日期名單！
                if (settings.data_fetch_strategy === "DAILY_FILE" ||
                    settings.data_fetch_strategy === "SINGLE_FILE") {
                    try {
                        const dateRes = await fetch(dirc_path + 'available_dates.json?t=' + Date.now());
                        if (dateRes.ok) {
                            availableDates = await dateRes.json();
                            
                            // 重新校正預設日期 (確保停留在有資料的那天)
                            currentDate = availableDates[availableDates.length - 1];
                            if (availableDates.includes(todayStr)) currentDate = todayStr;
                            else {
                                let futureDates = availableDates.filter(d => d >= todayStr);
                                if (futureDates.length > 0) currentDate = futureDates[0];
                            }
                            
                            // 更新設定檔
                            flatpickrConfig.defaultDate = currentDate;
                            flatpickrConfig.enable = availableDates; // 🌟 只有這裡才加上 enable 屬性！
                        }
                    } catch (e) {
                        console.warn("無法載入 available_dates.json，改為自由選擇日期");
                    }
                }

                // 4. 正式啟動日曆
                flatpickr(dateInput, flatpickrConfig);
            }

            // 🌟 通用營運日附註（如觀光線公休）：有 settings.calendar_note 才顯示
            let noteEl = document.getElementById('calendarNote');
            if (settings.calendar_note) {
                if (!noteEl) {
                    noteEl = document.createElement('div');
                    noteEl.id = 'calendarNote';
                    noteEl.className = 'calendar-note';
                    dateInput.parentNode.insertBefore(noteEl, dateInput.nextSibling);
                }
                noteEl.textContent = `ℹ️ ${settings.calendar_note}`;
                noteEl.style.display = '';
            } else if (noteEl) {
                noteEl.style.display = 'none';
            }

            // 啟動時載入選定的日期
            await loadTimetableData(currentDate);

        } else if (settings.calendar_type === "WEEKEND_SELECT") {
            // 🔘 情境 1 (南海、近鐵等私鐵)：使用平假日切換按鈕

            // 隱藏月曆與營運日附註
            if (dateInput) {
                dateInput.style.display = 'none';
                if (dateInput._flatpickr) dateInput._flatpickr.destroy();
            }
            let noteEl = document.getElementById('calendarNote');
            if (noteEl) noteEl.style.display = 'none';

            // 建立平假日切換按鈕 UI
            if (!btnContainer) {
                btnContainer = document.createElement('div');
                btnContainer.id = 'weekendSelectContainer';
                btnContainer.className = 'weekend-btn-group';
                dateInput.parentNode.insertBefore(btnContainer, dateInput.nextSibling);
            }
            btnContainer.innerHTML = '';
            btnContainer.style.display = 'flex'; // 確保顯示

            const btnWeekday = document.createElement('button');
            btnWeekday.innerText = '平日';
            btnWeekday.className = 'weekend-btn active'; 
            
            const btnHoliday = document.createElement('button');
            btnHoliday.innerText = '土休日';
            btnHoliday.className = 'weekend-btn';

            btnWeekday.onclick = async () => {
                btnWeekday.classList.add('active'); btnHoliday.classList.remove('active');
                currentDate = 'weekday'; await loadTimetableData('weekday');
            };

            btnHoliday.onclick = async () => {
                btnHoliday.classList.add('active'); btnWeekday.classList.remove('active');
                currentDate = 'holiday'; await loadTimetableData('holiday');
            };

            btnContainer.appendChild(btnWeekday);
            btnContainer.appendChild(btnHoliday);

            // 啟動預設載入平日
            currentDate = 'weekday';
            await loadTimetableData('weekday');
        } else {
            // 模式 B：單一檔案模式 (維持你原本的寫法)
            const timeRes = await fetch(dirc_path + 'timetable/timetable_20260420.json');
            timetable = await timeRes.json();
            optimizeTrainTimesForDisplay(timetable);
            interpolatePassingStations(timetable, topology);
        }
        // ==========================================

        
        buildUI();         // 建立側邊欄按鈕

        // 🌟🌟🌟 補上這一行：確保初始化時強制執行按鈕過濾！
        updateTrainTypeVisibility();

        updateBottomPanel(null); // 初始化底部面板
        bindThemeToggle(); // 啟動主題切換按鈕
        setupCanvasInteractions();
        setupBottomBarScrolling();
        setupSearch();

        // ==========================================
        // 🌟 終極修復：等待 CSS 排版完全穩定！
        // 讓瀏覽器停頓 0.1 秒，確保側邊欄就定位，畫布不再被推擠
        // ==========================================
        await new Promise(resolve => setTimeout(resolve, 100));
    
        // ==========================================
        // 🌟 終極修復 2：等待「所有自訂字體」下載完畢！
        // 解決 Canvas 一開始拿不到字體，印出醜醜預設字的 Bug
        // ==========================================
        await document.fonts.ready;

        document.body.offsetHeight;

        // ==========================================
        // 🌟 核心升級：套用高畫質 Canvas 解析度
        // ==========================================
        const canvasObj = initCanvas('diaCanvas', 'canvas-wrapper');
        
        // ⚠️ 注意：如果你的全域變數叫做 ctx，請把 ctx 替換為 canvasObj.ctx
        // 假設你的全域變數是 diaCanvas 或是 canvas，這裡重新賦值給它
        const canvas = canvasObj.canvas; 
        const ctx = canvasObj.ctx; // 讓後面的 redrawAll 可以用高畫質的筆刷來畫！

        // ==========================================
        // 🌟 啟動時強制執行一次滿版校正與「時間自動置中」
        // ==========================================
        redrawAll();      // 讓系統先算出預設路線的 loopKm
        autoFitScale();   // 算出最完美的 Y 軸拉伸比例
        camera.y = -50;   // 把畫面推到最頂端

        let currentMinutes = getCurrentSystemMinutes();

        // 鐵道標準跨夜處理：如果是凌晨 00:00 ~ 01:59，視為圖表上的 24:00 ~ 25:59
        if (currentMinutes < 120) {
            currentMinutes += 1440;
        }

        // 🌟 通用：若「現在時刻」落在今日班表的時間範圍外（如觀光線只在白天行駛、
        //    深夜開啟時 now 落在無車時段），改以班表時間中央為視窗中心，避免開圖一片空白。
        {
            let spanMin = Infinity, spanMax = -Infinity;
            for (const tr of timetable) {
                if (tr && tr._isYesterday) continue;
                for (const seg of (tr.segments || [])) {
                    for (const tv of seg.t) {
                        if (typeof tv === 'number' && !isNaN(tv)) {
                            if (tv < spanMin) spanMin = tv;
                            if (tv > spanMax) spanMax = tv;
                        }
                    }
                }
            }
            const SPAN_MARGIN = 30;
            if (spanMax > spanMin &&
                (currentMinutes < spanMin - SPAN_MARGIN || currentMinutes > spanMax + SPAN_MARGIN)) {
                currentMinutes = Math.round((spanMin + spanMax) / 2);
            }
        }

        // 算出現在時間在畫布上的真實 X 座標
        let targetX = timeToX(currentMinutes);
        
        // 取得螢幕寬度，將鏡頭的 X 座標設定為「目標 X 減去螢幕寬度的一半」達到完美置中
        const wrapper = document.getElementById('canvas-wrapper');
        let halfScreenWidth = wrapper ? wrapper.clientWidth / 2 : canvas.width / 2;
        camera.x = targetX - halfScreenWidth;

        // --- 結束新增 ---

        clampCamera();    // 撞牆防護：確保鏡頭不會超出邊界 (例如置中後左邊或右邊露出黑底)
        redrawAll();      // 畫出拉伸後、時間對準的最終完美畫面！     

        // ==========================================
        // 🌟 5. 圖畫完了！把轉圈圈優雅地隱藏起來
        // ==========================================
        setTimeout(() => {
            const loader = document.getElementById('loading-overlay');
            if (loader) {
                loader.classList.add('hidden'); // 觸發 CSS 淡出動畫
            }

        }, 400); // 🌟 把原本的 100 改成 400 毫秒，多給手機一點時間排版

        // ==========================================
        // 🌟 終極修正：啟動前先清掉舊的計時器，再綁定返回按鈕
        // ==========================================
        if (renderIntervalId) {
            clearInterval(renderIntervalId);
        }

        // 設定每分鐘自動重繪 (讓時間軸往前推)
        renderIntervalId = setInterval(() => {
            requestAnimationFrame(redrawAll);
        }, 60000);

        bindHomeButton(); // 綁定返回首頁按鈕

    } catch (e) {
        console.error("載入失敗:", e);
        // 🌟 防呆體驗：如果網路斷線或資料抓錯，把轉圈圈換成錯誤提示，不要讓使用者一直等
        const loader = document.getElementById('loading-overlay');
        if (loader) {
            loader.innerHTML = `<div style="color: #FF6666; font-size: 16px; font-weight: bold;">連線異常，載入失敗！<br><span style="font-size:12px; color:#AAA;">請檢查網路或重新整理 (F5)</span></div>`;
        }
    }
}

loadSystemMenu();