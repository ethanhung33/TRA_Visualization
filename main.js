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
// 2. 核心換算函式
// ==========================================
function timeToX(minutes) {
    return CONFIG.paddingLeft + (minutes * CONFIG.scaleX);
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
function drawGrid(viewKey) {
    lookupY = {}; 
    let currentAccumulatedKm = 0; 
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
                uniqueStations.push({ id: st.id, name: st.name, baseY: yPos });
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

    // 🌟 因為我們沒呼叫 initCanvas 了，所以這裡要負責把上一幀的舊圖擦掉
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    ctx.save();
    ctx.translate(-camera.x, -camera.y);

    // ... (下面維持你原本的畫橫線、畫時間標籤的迴圈邏輯) ...

    let copyStart = isCircular ? -1 : 0;
    let copyEnd = isCircular ? 1 : 0;

    for (let copy = copyStart; copy <= copyEnd; copy++) {
        let offsetY = isCircular ? ((copy * loopHeight) + CONFIG.paddingTop + loopHeight) : CONFIG.paddingTop;

        ctx.font = "bold 16px 'GlowSans', sans-serif";
        ctx.textBaseline = "middle";

        uniqueStations.forEach(st => {
            let y = st.baseY + offsetY;
            if (y < viewTop || y > viewBottom) return;

            // --- 畫背景橫線 ---
            let isHovered = (st.id === hoveredStation);
            let isSelected = (st.id === selectedStation);

            if (isSelected) {
                ctx.strokeStyle = "#FFD700"; // 點擊選中：亮黃色
                ctx.lineWidth = 2.0;
            } else if (isHovered) {
                ctx.strokeStyle = isDarkMode ? "#555555" : "#D0D0D0"; // 懸停：高反差白色/黑色
                ctx.lineWidth = 1.5;
            } else {
                ctx.strokeStyle = isDarkMode ? "#333333" : "#E0E0E0"; // 預設：低調的灰色
                ctx.lineWidth = 1.0;
            }

            ctx.beginPath();
            ctx.moveTo(CONFIG.paddingLeft, y);
            ctx.lineTo(CONFIG.paddingLeft + (1560 * CONFIG.scaleX), y);
            ctx.stroke();

            // --- 🌟 左右雙向懸浮站名 ---
            
            let maskBg = isDarkMode ? "rgba(0, 0, 0, 0.75)" : "rgba(255, 255, 255, 0.85)";
            let textColor = isDarkMode ? "#FFFFFF" : "#000000";
            let textWidth = ctx.measureText(st.name).width;

            // --- 左側站名 ---
            // 🌟 讓標籤跟隨攝影機，且距離左緣僅 10px
            let labelXLeft = Math.max(0, camera.x + 10); 
            ctx.fillStyle = maskBg;
            ctx.fillRect(labelXLeft - 5, y - 12, textWidth + 10, 24);
            ctx.fillStyle = textColor;
            ctx.textAlign = "left";
            ctx.fillText(st.name, labelXLeft, y);

            // --- 右側站名 ---
            // 🌟 距離右邊緣僅 10px
            let labelXRight = Math.min(CONFIG.paddingLeft + (1560 * CONFIG.scaleX) + 50, camera.x + wrapperW - 10);
            ctx.fillStyle = maskBg;
            ctx.fillRect(labelXRight - textWidth - 5, y - 12, textWidth + 10, 24);
            ctx.fillStyle = textColor;
            ctx.textAlign = "right";
            ctx.fillText(st.name, labelXRight, y);

            // --- 浮水印 (保持淡色) ---
            // ctx.font = "bold 24px 'GlowSans', sans-serif";
            // ctx.fillStyle = isDarkMode ? "rgba(200, 200, 200, 0.2)" : "rgba(100, 100, 100, 0.15)";
            // ctx.textAlign = "left";
            // for (let h = 1; h < 24; h += 2) { 
            //     let textX = timeToX(h * 60) + 5;
            //     if (textX > viewLeft && textX < viewRight) ctx.fillText(st.name, textX, y - 8); 
            // }
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

    for (let m = 0; m <= 1560; m += 10) {
        let x = timeToX(m);
        if (x < viewLeft - 50 || x > viewRight + 50) continue; 

        let isHourLine = (m % 60 === 0);
        ctx.beginPath();
        if (isHourLine) {
            ctx.strokeStyle = isDarkMode ? "#888888" : "#777777";
            ctx.lineWidth = 2.0;
        } else {
            ctx.setLineDash([3, 5]);
            ctx.strokeStyle = isDarkMode ? "#444444" : "#DDDDDD";
            ctx.lineWidth = 1.2;
        }
        
        // 🌟 使用新的邊界來畫線！
        ctx.moveTo(x, lineTop);                 
        ctx.lineTo(x, lineBottom);     
        ctx.stroke();
        ctx.setLineDash([]); 

        if (isHourLine) {
            let hour = m / 60;
            let timeStr = `${hour}:00`;
            ctx.font = "bold 18px 'GlowSans', sans-serif";
            ctx.textAlign = "center";
            let textWidth = ctx.measureText(timeStr).width;
            let maskBg = isDarkMode ? "rgba(0, 0, 0, 0.75)" : "rgba(255, 255, 255, 0.85)";
            let textColor = isDarkMode ? "#FFFFFF" : "#000000";

            // 🌟 頂部時間：貼近螢幕頂部，但不會超過路線最頂端
            let labelYTop = isCircular 
                ? Math.max(CONFIG.paddingTop - 25, camera.y + 30) 
                : Math.max(routeStartY - 25, Math.min(camera.y + 30, routeEndY));

            // 🌟 底部時間：貼近螢幕底部，但如果路線很短，會自動「吸附」在路線底下，不會掉進黑洞！
            let labelYBottom = isCircular 
                ? camera.y + wrapperH - 30 
                : Math.min(camera.y + wrapperH - 30, routeEndY + 30);

            // 畫頂部
            ctx.fillStyle = maskBg;
            ctx.fillRect(x - textWidth/2 - 5, labelYTop - 15, textWidth + 10, 22);
            ctx.fillStyle = textColor;
            ctx.fillText(timeStr, x, labelYTop + 2);

            // 畫底部
            ctx.fillStyle = maskBg;
            ctx.fillRect(x - textWidth/2 - 5, labelYBottom - 15, textWidth + 10, 22);
            ctx.fillStyle = textColor;
            ctx.fillText(timeStr, x, labelYBottom + 2);
        }
    }
    ctx.restore(); 
}

function getJunction(st1_id, st2_id) {
    if (!st1_id || !st2_id || st1_id === st2_id) return null;
    let cacheKey = st1_id + "-" + st2_id;
    if (junctionCache[cacheKey] !== undefined) return junctionCache[cacheKey];

    // 找出包含這兩個站的路線段
    let segs1 = topology.segments.filter(s => s.stations.some(st => st.id === st1_id));
    let segs2 = topology.segments.filter(s => s.stations.some(st => st.id === st2_id));

    for (let s1 of segs1) {
        for (let s2 of segs2) {
            if (s1.id === s2.id) continue;
            let ids1 = s1.stations.map(st => st.id);
            let junc = s2.stations.find(st => ids1.includes(st.id));
            if (junc) {
                junctionCache[cacheKey] = junc.id;
                return junc.id;
            }
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
    const viewBottom = camera.y + canvas.height + 200;
    const viewLeft = camera.x - 200;
    const viewRight = camera.x + canvas.width + 200;

    let presetKey = currentRouteView; 
    let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
    let copyStart = isCircular ? -1 : 0;
    let copyEnd = isCircular ? 1 : 0;

    let colorIndex = isDarkMode ? 0 : 1;
    let fallbackColor = isDarkMode ? "#FFFFFF" : "#000000";

    ctx.save();
    ctx.translate(-camera.x, -camera.y);

    // ==========================================
    // 🌟 終極裁切遮罩 (Clip)：切除超界跨夜車與左側重疊
    // ==========================================
    ctx.beginPath();
    // 起點 X：CONFIG.paddingLeft (剛好閃過左邊的站名留白區)
    // 起點 Y：viewTop (確保上下無限延伸不被切到)
    // 寬度：1560 * CONFIG.scaleX (從 0:00 完美切齊 26:00 的那一條線)
    // 高度：viewBottom - viewTop (涵蓋攝影機的可視範圍)
    ctx.rect(CONFIG.paddingLeft, viewTop, 1560 * CONFIG.scaleX, viewBottom - viewTop);
    ctx.clip(); // ✂️ 喀嚓！超出這個隱形方塊的火車折線通通不准畫！

    // ==========================================
    // 🌟 新增：把「畫一台車」的邏輯打包起來
    // ==========================================
    // 🌟 在小括號裡面多加一個 isHovered 參數
    const drawSingleTrain = (train, isVIP, isHovered) => {
        // ==========================================
        // 🌟 1. 先決定這台車「原本的」顏色和粗細
        // ==========================================
        let baseColor = fallbackColor;
        let baseWidth = train.w || 1.5; // 通用的保底粗細 (如果設定檔沒寫，預設 1.5)

        if (settings && settings.train_color && settings.train_color[train.type]) {
            let typeStyle = settings.train_color[train.type];
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
        if (isVIP) {
            trainColor = '#FFD700'; // 點擊：亮黃色粗線
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
                
                ctx.beginPath();
                let isDrawing = false; 

                // ==========================================
                // 🌟🌟🌟 新增這行：只要畫布起了一個新的頭，麵包屑就強制斷開！避免產生隱形連線！
                // ==========================================
                train._hitPoints.push(null);

                for (let i = 0; i < seg.s.length; i++) {
                    let y_raw = unwrappedCoords[i];
                    if (y_raw === null) { 
                        isDrawing = false; 
                        // 🌟 【新增 2】：如果線條中斷，塞入 null 斷開麵包屑
                        train._hitPoints.push(null); 
                        continue; 
                    }

                    let y = y_raw + offsetY; 
                    let x_arr = timeToX(seg.t[i * 2]);
                    let x_dep = timeToX(seg.t[i * 2 + 1]);

                    // 🌟 【新增 3】：把算好的真實座標存起來 (這就是麵包屑！)
                   
                    train._hitPoints.push({ x: x_arr, y: y });
                    // 如果這站有停 (v !== 2)，代表進出站會是一條水平線，也要記錄出站點
                    if (seg.v[i] !== 2) {
                        train._hitPoints.push({ x: x_dep, y: y });
                    }
                    

                    if (!isDrawing) { 
                        if (i === 0 && segIdx > 0) {
                            ctx.moveTo(x_dep, y); 
                        } else {
                            ctx.moveTo(x_arr, y); 
                        }
                        isDrawing = true; 
                    } else { 
                        ctx.lineTo(x_arr, y); 
                    }

                    // 🌟 改成下面這樣 (直接把 else 刪掉！)：
                    if (seg.v[i] !== 2) {
                        ctx.lineTo(x_dep, y);
                    }
                    // 解說：如果是通過站 (v === 2)，我們什麼都不做！
                    // 讓畫筆繼續貼在紙上，下一個 lineTo 就會畫出完美的連續直線，不再斷裂！
                }
                ctx.stroke();
                // ==========================================
                // 🌟 新增：線畫完後，如果是 VIP，就在旁邊加上站名與時間！
                // ==========================================
                if (isVIP) {
                    ctx.save(); // 保護畫筆狀態，不要干擾到其他車

                    for (let i = 0; i < seg.s.length; i++) {
                        let y_raw = unwrappedCoords[i];
                        if (y_raw === null) continue; // 遇到斷點跳過

                        if (seg.v[i] === 2) continue;
                        
                        let y = y_raw + offsetY;
                        let arrT = seg.t[i * 2];
                        let depT = seg.t[i * 2 + 1];
                        let x_dep = timeToX(depT); // 文字要對齊出站的 X 座標


                        // --- 2. 準備文字：站名與時間 ---
                        // ⚠️ A. 取得站名 (請替換成你系統中將 ID 轉成中文的函數)
                        let stationName = getStationName(seg.s[i]);
                        
                        // ⚠️ B. 取得時間 (請替換成你系統中將數字轉成 HH:MM 的函數)
                        // 如果你沒有，請把它丟進下面我附贈的 formatTimeDisplay 函數
                        let arrTimeStr = formatTimeDisplay(arrT); 
                        let depTimeStr = formatTimeDisplay(depT); 

                        // 組裝字串：如果到站=離站(通過/首尾站)，就只顯示一個時間
                        let displayText = `${arrTimeStr} - ${depTimeStr} ${stationName}`;

                        // --- 3. 畫出文字 ---
                        ctx.font = '14px "GlowSans", "Segoe UI", sans-serif'; 
                        ctx.fillStyle = isDarkMode ? '#FFFFFF' : '#000000'; // 白字或黑字
                        ctx.textAlign = 'left';
                        ctx.textBaseline = 'middle';
                        
                        // 💡 視覺小秘訣：加一點點反色陰影，讓文字在密密麻麻的線條海中不會糊掉
                        ctx.shadowColor = isDarkMode ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.8)';
                        ctx.shadowBlur = 4;

                        // 在 X 座標往右推 8 px 的地方畫字
                        ctx.fillText(displayText, x_dep + 8, y);
                    }

                    ctx.restore(); // 恢復畫筆，準備畫下一台車
                }
            }
        });
    };
    // ==========================================
    // 結束打包
    // ==========================================


    // 🌟 真正的繪圖流程開始！(分三層畫)
    let vipTrain = null;
    let hoverTrainDraw = null;

    // 第一次迴圈：畫普通車，把 VIP 和 Hover 扣留起來
    timetable.forEach(train => {
        
        // ==========================================
        // 🌟 終極淨化術：在做任何判斷前，無條件清空這台車的物理座標！
        // 這樣就算它等一下被隱藏，也絕對不會留下「幽靈點」讓滑鼠點到！
        // ==========================================
        if (!train._hitPoints) train._hitPoints = [];
        train._hitPoints.length = 0; 
        // ==========================================

        // 1. 車種過濾檢查
        if (!activeTrainTypes.has(train.type)) {
            return; 
        }

        // 2. 停靠站聚焦過濾器 (Focus Mode)
        if (selectedStation) {
            let stopsHere = false;
            if (train.segments) {
                for (let seg of train.segments) {
                    for (let i = 0; i < seg.s.length; i++) {
                        // 檢查：1. 站碼是不是我們點擊的站  2. v !== 2 代表「有停靠」
                        if (String(seg.s[i]) === String(selectedStation) && seg.v[i] !== 2) {
                            stopsHere = true;
                            break;
                        }
                    }
                    if (stopsHere) break;
                }
            }
            // 如果這台車沒有停靠這個車站，就直接跳過，讓他在畫面上隱形！
            // (而且因為上面已經清空了 _hitPoints，它現在連物理實體都沒有了！)
            if (!stopsHere) {
                return; 
            }
        }

        // 3. 狀態判斷與分發
        if (train === selectedTrain) {
            vipTrain = train;
        } else if (train === hoveredTrain) {
            hoverTrainDraw = train;
        } else {
            drawSingleTrain(train, false, false); 
        }
    });

    // 第二次：畫懸停的車 (壓在普通車上面)
    if (hoverTrainDraw) drawSingleTrain(hoverTrainDraw, false, true); 

    // 第三次：畫點擊的 VIP 車 (永遠壓在最上面)
    if (vipTrain) drawSingleTrain(vipTrain, true, false); 

    ctx.restore();
}

// ==========================================
// 🕒 繪製現在時間線 (跨夜影分身 + 智慧邊界版)
// ==========================================
function drawCurrentTimeLine() {
    const now = new Date();
    let currentMinutes = now.getHours() * 60 + now.getMinutes();

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
            
            ctx.fillText(now.getHours() + ":" + now.getMinutes().toString().padStart(2, '0'), x + 8, labelY);
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
}

function buildUI() {
    // ---- 取得當下主題色碼的輔助函數 ----
    function getColor(colorsArray) {
        if (!colorsArray) return isDarkMode ? "#555" : "#CCC";
        return isDarkMode ? colorsArray[0] : colorsArray[1];
    }

    // ---- A. 🌟 動態產生路線切換按鈕 ----
    const routeContainer = document.getElementById('route-type-container');
    if (routeContainer) routeContainer.innerHTML = ''; 

    // 抓出 setting.json 裡面所有的視角 key (例如 'mountain_view', 'north_link')
    const viewKeys = Object.keys(settings?.view_presets || {});

    // ==========================================
    // 🌟 新增：如果視角只有 1 個(或沒有)，直接把整個切換區塊隱藏！
    // ==========================================
    if (viewKeys.length <= 1) {
        if (routeContainer) routeContainer.style.display = 'none';
        
        // 順便把旁邊可能有的 "路線" 標題也隱藏 (如果你 HTML 裡有寫的話)
        let routeTitle = document.getElementById('route-title');
        if (routeTitle) routeTitle.style.display = 'none';
    } else {
        if (routeContainer) routeContainer.style.display = ''; // 恢復預設顯示
        let routeTitle = document.getElementById('route-title');
        if (routeTitle) routeTitle.style.display = '';
    }
    
    // 🌟 核心防呆：如果目前記憶的視角「不在」新系統的視角清單中，就強制洗掉重置！
    if (viewKeys.length > 0 && !viewKeys.includes(currentRouteView)) {
        currentRouteView = viewKeys[0];
    }

    // 建立一個陣列把產生的按鈕存起來，方便切換時改顏色
    const dynamicRouteBtns = [];

    const updateRouteButtons = () => {
        let defaultBg = isDarkMode ? "#444444" : "#E0E0E0";
        let defaultBorder = isDarkMode ? "#555555" : "#CCCCCC";
        let defaultText = isDarkMode ? "#CCCCCC" : "#000000";
        let selectedText = isDarkMode ? "#000000" : "#FFFFFF";

        dynamicRouteBtns.forEach(item => {
            let btn = item.btn;
            if (currentRouteView === item.key) {
                // 如果是被選中的路線，就抓 json 裡設定的專屬顏色
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
    };

    // 迴圈跑出所有按鈕
    viewKeys.forEach(key => {
        const preset = settings.view_presets[key];
        const btn = document.createElement('button');
        btn.className = 'pill-btn';
        btn.textContent = preset.name; // 這裡會印出 "山線環島鐵路" 或 "縱貫線北段"
        
        btn.addEventListener('click', () => handleRouteSwitch(key));
        
        if (routeContainer) routeContainer.appendChild(btn);
        dynamicRouteBtns.push({ key: key, btn: btn });
    });

    window.updateRouteButtons = updateRouteButtons; 
    updateRouteButtons();

    // ---- B. 動態生成車種篩選按鈕 (通用萬用版，免寫 train_order) ----
    
    // 1. 抓出時刻表內實際有出現的車種集合
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

    // 4. 使用排好序的 sortedTypes 來生成按鈕
    sortedTypes.forEach(type => {
        activeTrainTypes.add(type);

        const btn = document.createElement('button');
        btn.className = 'pill-btn';
        btn.textContent = type;
        
        // 🌟 車種按鈕的配色邏輯
        const updateTrainBtnStyle = () => {
            let defaultBg = isDarkMode ? "#444444" : "#E0E0E0";
            let defaultBorder = isDarkMode ? "#555555" : "#CCCCCC";
            let defaultText = isDarkMode ? "#CCCCCC" : "#000000";
            let selectedText = isDarkMode ? "#000000" : "#FFFFFF";

            if (activeTrainTypes.has(type)) {
                let tColor = getColor(settings?.train_color?.[type]);
                btn.style.backgroundColor = tColor;
                btn.style.borderColor = tColor;
                btn.style.color = selectedText;
            } else {
                btn.style.backgroundColor = defaultBg;
                btn.style.borderColor = defaultBorder;
                btn.style.color = defaultText;
            }
        };

        updateTrainBtnStyle();
        btn._updateStyle = updateTrainBtnStyle; 

        btn.addEventListener('click', () => {
            if (activeTrainTypes.has(type)) activeTrainTypes.delete(type);
            else activeTrainTypes.add(type);
            updateTrainBtnStyle();
            
            syncBottomPanel(); // 🌟 1. 單一按鈕點擊時：同步更新面板！
            redrawAll();
        });
        trainTypeContainer.appendChild(btn);
    });

    // ==========================================
    // 🌟 修正：將 addEventListener 改成 onclick
    // ==========================================
    // 全選 
    btnAllTrains.onclick = () => {
        activeTrainTypes = new Set(sortedTypes);
        document.querySelectorAll('#train-type-container .pill-btn').forEach(b => { if(b._updateStyle) b._updateStyle(); });
        
        syncBottomPanel();
        redrawAll();
    };

    // 全部不選
    btnNoTrains.onclick = () => {
        activeTrainTypes.clear();
        document.querySelectorAll('#train-type-container .pill-btn').forEach(b => { if(b._updateStyle) b._updateStyle(); });
        
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
// 🖱️ 底部面板：將滑鼠上下滾輪轉換為左右滑動
// ==========================================
function setupBottomBarScrolling() {
    const bottomBar = document.getElementById('bottom-bar');
    if (!bottomBar) return;

    // { passive: false } 是必須的，這樣我們才能呼叫 e.preventDefault() 停用預設滾動
    bottomBar.addEventListener('wheel', (e) => {
        const scrollContainer = document.getElementById('bottom-scroll-container');
        
        if (scrollContainer) {
            // 🌟 1. 防止整個網頁被上下捲動
            e.preventDefault(); 
            
            // 🌟 2. 極度關鍵：防止事件往上傳遞給 Canvas！
            // 這樣在底部面板滾輪時，上面的地圖就不會跟著放大縮小！
            e.stopPropagation(); 
            
            // 🌟 3. 將滾輪的上下幅度 (deltaY) 轉移給容器的左右捲動軸 (scrollLeft)
            // 加上一個倍率(例如 1.5) 可以讓滑動感覺更順暢、更快
            scrollContainer.scrollLeft += (e.deltaY * 1.5); 
        }
    }, { passive: false });
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

            // 強制校正鏡頭邊界並重繪
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

// 統整重繪動作 (清空 -> 畫網格 -> 畫火車)
function redrawAll() {
    clampCamera();
    
    // ==========================================
    // 🌟 終極防模糊殺手鐧：強制攝影機對齊「實體像素」！
    // 徹底消滅因為小數點座標造成的次像素模糊 (Sub-pixel blur)
    // ==========================================
    camera.x = Math.round(camera.x);
    camera.y = Math.round(camera.y);

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawGrid(currentRouteView); 
    drawTrains();
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

        // ==========================================
        // 🌟 核心修復：在重新渲染面板前，先「記住」目前的左右滾動進度！
        // ==========================================
        const scrollContainer = document.getElementById('bottom-scroll-container');
        let savedScrollLeft = scrollContainer ? scrollContainer.scrollLeft : 0;

        if (selectedStation) {
            updateBottomPanelStation(selectedStation);
        }
        else if (selectedTrain) {
            updateBottomPanel(selectedTrain);
        }

        // ==========================================
        // 🌟 重新抓取剛畫好的新面板，把滾動進度「還給」它！
        // ==========================================
        const newScrollContainer = document.getElementById('bottom-scroll-container');
        if (newScrollContainer) {
            newScrollContainer.scrollLeft = savedScrollLeft;
        }

        // 4. 重繪畫布
        redrawAll();
    });
}

// ==========================================
// 🌟 視角自動適應 (防過度壓縮 + 支援預設縮放版)
// ==========================================
function autoFitScale() {
    const wrapper = document.getElementById('canvas-wrapper');
    if (!wrapper || typeof loopKm === 'undefined' || loopKm <= 0) return;

    // 算出 Y 軸要「完美塞滿螢幕」所需要的最低倍率
    const minScaleY = (wrapper.clientHeight - 150) / loopKm;

    // 讀取時間拉伸係數
    let timeStretchRatio = 0.4;
    if (settings && settings.time_stretch_ratio !== undefined) {
        timeStretchRatio = settings.time_stretch_ratio;
    }

    // 🌟 核心修改：不再無腦硬塞滿螢幕！
    let targetScaleY = minScaleY;

    // 1. 如果設定檔有明確指示「預設放大倍率」，絕對聽設定檔的！
    if (settings && settings.default_scale_y !== undefined) {
        targetScaleY = settings.default_scale_y;
    } 
    // 2. 如果沒設定，且路線太長導致比例被壓得太扁 (例如小於 2.0)，強制放大，讓使用者自己滾動
    else if (minScaleY < 2.0) {
        targetScaleY = 2.0; 
    }

    // 正式套用比例
    CONFIG.scaleY = targetScaleY;
    CONFIG.scaleX = targetScaleY * timeStretchRatio; 
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
    // 如果 loopHeight 還沒計算出來，或是目前的視角不是循環模式，就跳過
    if (loopHeight <= 0) return;

    // 取得目前的視圖類型 (判斷是否為 CIRCULAR)
    let presetKey = currentRouteView; 
    let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
    
    if (!isCircular) return;

    // 🌟 核心邏輯：
    // 我們畫了三圈 (copy -1, 0, 1)，我們希望攝影機儘量待在中間那一圈 (copy 0)。
    // 中間圈的起始 Y 座標是 CONFIG.paddingTop + loopHeight。

    const centerPoint = CONFIG.paddingTop + loopHeight;

    // 如果攝影機往上跑太遠，就把它往下瞬移一整圈
    if (camera.y < centerPoint - loopHeight * 0.5) {
        camera.y += loopHeight;
    } 
    // 如果攝影機往下跑太遠，就把它往上瞬移一整圈
    else if (camera.y > centerPoint + loopHeight * 0.5) {
        camera.y -= loopHeight;
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

        const minScaleX = (wrapperW - safeMargin * 2) / 1560;
        const minScaleY = wrapperH / safeLoopKm;

        if (zoom < 1) {
            let minAllowedZoom = Math.min(minScaleX / CONFIG.scaleX, minScaleY / CONFIG.scaleY);
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

        let closestTrain = null, minDistance = 20; // 胖手指容錯率加大

        if (typeof timetable !== 'undefined') {
            for (let train of timetable) {
                if (typeof activeTrainTypes !== 'undefined' && !activeTrainTypes.has(train.type)) continue;

                // ==========================================
                // 🌟 新增防護罩：如果現在有鎖定車站，但這台車沒停，就讓它物理穿透！
                // ==========================================
                if (selectedStation) {
                    let stopsHere = false;
                    if (train.segments) {
                        for (let seg of train.segments) {
                            for (let i = 0; i < seg.s.length; i++) {
                                // 檢查是否為選定站，且有停靠 (v !== 2)
                                if (String(seg.s[i]) === String(selectedStation) && seg.v[i] !== 2) {
                                    stopsHere = true; 
                                    break;
                                }
                            }
                            if (stopsHere) break;
                        }
                    }
                    // 如果這台車沒停靠這個車站，直接跳過點擊判定！
                    if (!stopsHere) continue; 
                }
                // ==========================================

                if (!train._hitPoints) continue;
                for (let i = 0; i < train._hitPoints.length - 1; i++) {
                    let p1 = train._hitPoints[i], p2 = train._hitPoints[i+1];
                    if (!p1 || !p2) continue;
                    let dist = getDistanceToSegment(worldX, worldY, p1.x, p1.y, p2.x, p2.y);
                    // 🌟 順便縮小一點胖手指容錯率 (從 20 降到 15)，減少誤觸機率
                    if (dist < 15 && dist < minDistance) { 
                        minDistance = dist; 
                        closestTrain = train; 
                    }
                }
            }
        }

        if (closestTrain) {
            selectedTrain = closestTrain; selectedStation = null;
            if (typeof updateBottomPanel === 'function') updateBottomPanel(selectedTrain);
        } else {
            let closestStationId = null, minStationDist = 10; 
            let isCircular = false;
            if (typeof settings !== 'undefined' && settings?.view_presets?.[currentRouteView]?.view_type === "CIRCULAR") {
                isCircular = true;
            }
            
            let safeLoopH = (typeof loopHeight !== 'undefined') ? loopHeight : 0;

            if (typeof lookupY !== 'undefined') {
                for (let st_id in lookupY) {
                    for (let opt of lookupY[st_id]) {
                        for (let copy = (isCircular ? -1 : 0); copy <= (isCircular ? 1 : 0); copy++) {
                            let offsetY = isCircular ? ((copy * safeLoopH) + CONFIG.paddingTop + safeLoopH) : CONFIG.paddingTop;
                            if (Math.abs(worldY - (opt.y + offsetY)) < minStationDist) {
                                minStationDist = Math.abs(worldY - (opt.y + offsetY));
                                closestStationId = st_id;
                            }
                        }
                    }
                }
            }

            if (closestStationId) {
                selectedStation = closestStationId; selectedTrain = null;
                if (typeof updateBottomPanelStation === 'function') updateBottomPanelStation(selectedStation);
            } else {
                selectedTrain = null; selectedStation = null;
                if (typeof updateBottomPanel === 'function') updateBottomPanel(null);
            }
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
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            // 🌟 將滑鼠座標轉換為「真實世界座標」(加上攝影機的偏移量)
            // 這樣不管是找火車還是找車站，數學計算都會更精準簡單！
            const worldX = mouseX + camera.x;
            const worldY = mouseY + camera.y;

            let hitTrain = null;
            let hitStation = null;

            // ==========================================
            // 📡 雷達 1：偵測火車 (精準線段掃描)
            // ==========================================
            for (let train of timetable) {

                // ==========================================
                // 🌟 新增防護罩：游標懸停時也一樣，沒停靠的車變成幽靈！
                // ==========================================
                if (selectedStation) {
                    let stopsHere = false;
                    if (train.segments) {
                        for (let seg of train.segments) {
                            for (let i = 0; i < seg.s.length; i++) {
                                if (String(seg.s[i]) === String(selectedStation) && seg.v[i] !== 2) {
                                    stopsHere = true; 
                                    break;
                                }
                            }
                            if (stopsHere) break;
                        }
                    }
                    // 如果這台車沒停靠這個車站，直接跳過懸停判定！
                    if (!stopsHere) continue; 
                }
                // ==========================================

                // 如果火車被隱藏或點不到兩個，跳過
                if (!train._hitPoints || train._hitPoints.length < 2) continue; 
                
                for (let i = 0; i < train._hitPoints.length - 1; i++) {
                    let p1 = train._hitPoints[i];
                    let p2 = train._hitPoints[i+1];
                    
                    // 防呆：如果遇到 null (代表路線斷開)，就跳過這段不計算
                    if (!p1 || !p2) continue; 
                    
                    // 🌟 核心升級：使用「點到線段的垂直距離」來計算！
                    let dist = getDistanceToSegment(worldX, worldY, p1.x, p1.y, p2.x, p2.y);
                    
                    // 容錯範圍：只要距離線條小於 6 像素，就視為碰到火車！
                    if (dist < 6) {
                        hitTrain = train;
                        break; 
                    }
                }
                if (hitTrain) break; 
            }

            // ==========================================
            // 📡 雷達 2：偵測車站 (掃描 Y 軸座標)
            // 只有在沒碰到火車時，才去尋找車站 (火車優先級較高)
            // ==========================================
            if (!hitTrain) {
                let minStationDist = 12; // 🌟 車站的垂直感應範圍 (12px)
                let isCircular = settings?.view_presets?.[currentRouteView]?.view_type === "CIRCULAR";
                let safeLoopH = loopHeight || 0;

                if (typeof lookupY !== 'undefined') {
                    for (let st_id in lookupY) {
                        for (let opt of lookupY[st_id]) {
                            // 檢查本尊與上下影分身 (環狀線)
                            for (let copy = (isCircular ? -1 : 0); copy <= (isCircular ? 1 : 0); copy++) {
                                let offsetY = isCircular ? ((copy * safeLoopH) + CONFIG.paddingTop + safeLoopH) : CONFIG.paddingTop;
                                let stationY = opt.y + offsetY;
                                
                                // 如果滑鼠的 Y 座標距離這條車站橫線很近！
                                if (Math.abs(worldY - stationY) < minStationDist) {
                                    minStationDist = Math.abs(worldY - stationY);
                                    hitStation = st_id;
                                }
                            }
                        }
                    }
                }
            }

            // ==========================================
            // 🌟 狀態更新與重繪判定
            // ==========================================
            let statusChanged = false;
            
            if (hitTrain !== hoveredTrain) {
                hoveredTrain = hitTrain;
                statusChanged = true;
            }
            
            if (hitStation !== hoveredStation) {
                hoveredStation = hitStation;
                statusChanged = true;
            }

            // 只要火車或車站任何一個的 Hover 狀態改變了，就立刻重繪！
            if (statusChanged) {
                // 如果碰到火車或車站，游標變成手指 👆
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
    // ⌨️ 全域鍵盤事件：按下 ESC 取消選取
    // ==========================================
    window.addEventListener('keydown', (e) => {
        // 檢查按下的鍵是不是 ESC
        if (e.key === 'Escape') {
            // 如果現在有選取火車或車站，才去執行清空動作
            if (selectedTrain || selectedStation) {
                
                // 1. 清空選取狀態變數
                selectedTrain = null;
                selectedStation = null;
                
                // 2. 恢復底部面板為預設狀態 ("點選列車或車站以顯示資訊")
                if (typeof updateBottomPanel === 'function') {
                    updateBottomPanel(null);
                }
                
                // 3. 重新繪製畫布，把黃色高光線條或發光的車站橫線擦掉
                if (typeof requestRedraw === 'function') {
                    requestRedraw();
                } else if (typeof redrawAll === 'function') {
                    redrawAll();
                }
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
    if (minutesRaw === undefined || minutesRaw === null) return "--:--";
    
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
        return;
    }

    // 1. 取得車次與顏色
    let trainNo = train.no || train.train_no || train.id || "未知";
    let trainType = train.type || "";
    
    let trainColor = "#888888"; 
    if (settings && settings.train_color && settings.train_color[trainType]) {
        trainColor = settings.train_color[trainType][isDarkMode ? 0 : 1]; 
    }

    // 🌟 核心修改：如果設定檔明確寫了 false，就只顯示車次；否則顯示「車種 車次」
    let displayTitle = (settings && settings.show_train_type === false) 
        ? trainNo 
        : `${trainType} ${trainNo}`;

    // ==========================================
    // 🌟 新增：自動抓取這班車的「起點」與「終點」 (使用 getStationName 最終版)
    // ==========================================
    let startStationName = "未知";
    let endStationName = "未知";

    // 優先檢查原始資料有沒有自帶起終點
    if (train.start_station_name) {
        startStationName = train.start_station_name;
        endStationName = train.end_station_name;
    } else if (train.segments && train.segments.length > 0) {
        let firstSeg = train.segments[0];
        let lastSeg = train.segments[train.segments.length - 1];
        
        let startId = firstSeg.s[0];
        let endId = lastSeg.s[lastSeg.s.length - 1];
        
        // 🌟 直接呼叫你系統原生的 getStationName 函數！
        if (typeof getStationName === 'function') {
            startStationName = getStationName(startId);
            endStationName = getStationName(endId);
        }
    }

    // 2. 組裝車站列表的 HTML
    let stationsHtml = "";
    let stopCount = 0;

    let lastStationId = null;

    if (train.segments) {
        train.segments.forEach(seg => {
            for (let i = 0; i < seg.s.length; i++) {
                if (seg.v[i] === 2) continue; // 過濾掉通過的車站

                let currentStationId = seg.s[i];

                // 🌟 新增這段過濾機制：
                // 如果現在這個車站，跟上一個剛剛印過的車站一模一樣，就直接跳過！
                if (currentStationId === lastStationId) {
                    continue;
                }
                lastStationId = currentStationId;

                let stName = getStationName(seg.s[i]);
                // 如果你沒有 formatTimeDisplay 函數，請確保把它也加進 main.js 喔！
                let arrT = formatTimeDisplay(seg.t[i * 2]);     
                let depT = formatTimeDisplay(seg.t[i * 2 + 1]); 
                
                // 🌟 別忘了中間的箭頭也可以加大
                if (stopCount > 0) {
                    stationsHtml += `
                        <div style="display: flex; align-items: center; justify-content: center; margin: 0 12px; font-size: 20px; color: var(--panel-arrow);">
                            ➔
                        </div>
                    `;
                }

                // 在產生 stationsHtml 的迴圈內
                stationsHtml += `
                    <div onclick="window.triggerSelectStation('${seg.s[i]}')" 
                         style="display: flex; flex-direction: column; align-items: center; min-width: 70px; cursor: pointer; padding: 8px; border-radius: 8px; transition: background 0.2s;"
                         onmouseover="this.style.background='rgba(128,128,128,0.2)'"
                         onmouseout="this.style.background='transparent'">
                         
                        <div style="font-size: 20px; margin-bottom: 6px; font-weight: bold; letter-spacing: 1px; color: var(--panel-text-main);">
                            ${stName}
                        </div>
                        
                        <div style="font-size: 15px; line-height: 1.4; color: var(--panel-text-sub);">${arrT}</div>
                        <div style="font-size: 15px; line-height: 1.4; color: var(--panel-text-sub);">${depT}</div>
                    </div>
                `;

                
                stopCount++;
            }
        });
    }

    // 3. 塞進現有的 bottom-bar
    panel.innerHTML = `
        <div style="display: flex; width: 100%; height: 100%; align-items: center;">
            
            <div style="min-width: 180px; display: flex; flex-direction: column; justify-content: center; padding-left: 25px; padding-right: 20px; border-right: 2px solid #444; flex-shrink: 0;">
                <div style="font-size: 26px; font-weight: 900; color: ${trainColor}; letter-spacing: 1px; line-height: 1.0;">
                    ${displayTitle}
                </div>
                
                <div style="font-size: 16px; color: ${isDarkMode ? '#E0E0E0' : '#333333'}; opacity: 0.9; margin-top: 10px; font-weight: bold; letter-spacing: 1px;">
                    ${startStationName} <span style="font-size:14px; margin: 0 4px; opacity: 0.7;">▶</span> ${endStationName}
                </div>
            </div>
            
            <div id="bottom-scroll-container" style="flex: 1; display: flex; align-items: center; overflow-x: auto; padding: 0 20px; white-space: nowrap; scrollbar-width: none;">
                ${stationsHtml}
            </div>
        </div>
    `;
}

// ==========================================
// 🚉 更新底部面板 (精簡雙排行 + 高效能幾何方向版)
// ==========================================
function updateBottomPanelStation(st_id) {
    const panel = document.getElementById('bottom-bar'); 
    if (!panel) return;

    let stName = getStationName(st_id);
    const now = new Date();
    let currentMinutes = now.getHours() * 60 + now.getMinutes();

    // 🌟 回歸兩大陣營：只分 上行(北上) 與 下行(南下)
    let upboundTrains = [];
    let downboundTrains = [];

    let processedTrains = new Set();

    // 1. 尋找即將發車的班次
    timetable.forEach(train => {
        if (!activeTrainTypes.has(train.type) || !train.segments) return;

        let trainNo = train.no || train.train_no || "未知";

        if (processedTrains.has(trainNo)) return;

        for (let segIdx = 0; segIdx < train.segments.length; segIdx++) {
            
            // 🌟 核心修復：如果這班車已經在前面的線段被加進去了，就直接強制打斷，不要再找下一段了！
            if (processedTrains.has(trainNo)) break; 

            let seg = train.segments[segIdx];

            for (let i = 0; i < seg.s.length; i++) {
                if (seg.s[i] === st_id && seg.v[i] !== 2 && seg.v[i] !== 3) {
                    let depT = seg.t[i * 2 + 1];
                    
                    // 鐵道標準「營業日」時間轉換
                    let opsNow = currentMinutes < 120 ? currentMinutes + 1440 : currentMinutes;
                    let opsDep = depT < 120 ? depT + 1440 : depT;
                    
                    let diff = opsDep - opsNow;

                    if (diff >= 0 && opsDep >= opsNow) {
                        
                        // ==========================================
                        // 🌟 終極方案：絕對里程判定法 (Data-Driven Radar)
                        // 拋棄畫布座標，直接從 topology 底層資料庫比對真實里程！
                        // ==========================================
                        let isUpbound = true; 
                        let foundDirection = false;

                        // 1. 抓出這班車的「下一站」是誰？
                        let nextStId = null;
                        if (i + 1 < seg.s.length) {
                            nextStId = seg.s[i + 1]; // 同一條線段的下一站
                        } else if (segIdx + 1 < train.segments.length) {
                            nextStId = train.segments[segIdx + 1].s[0]; // 跨線段的第一站
                        }

                        // 2. 去 topology.json (實體路線圖) 查水表！
                        if (nextStId && topology && topology.segments) {
                            for (let topoSeg of topology.segments) {
                                // 找找看這條實體線有沒有包含這兩個站
                                let currSt = topoSeg.stations.find(s => String(s.id) === String(st_id));
                                let nextSt = topoSeg.stations.find(s => String(s.id) === String(nextStId));
                                
                                // 🌟 核心防呆：必須確保這兩個站「都在同一條實體線上」，才能互相比較里程！
                                // 這樣就可以完美避開「交會站 (如新竹、八堵)」的影分身問題！
                                if (currSt && nextSt && currSt.km !== undefined && nextSt.km !== undefined) {
                                    if (currSt.km !== nextSt.km) {
                                        
                                        // 🚂 鐵路物理鐵律：
                                        // 里程變小 (往起點開) = ▲ 上行
                                        // 里程變大 (往終點開) = ▼ 下行
                                        isUpbound = (nextSt.km < currSt.km);
                                        foundDirection = true;
                                        break;
                                    }
                                }
                            }
                        }

                        // 3. 🛡️ 終極保底機制 (如果這是一站到底的車，或是下一站剛好不在資料庫)
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
                        // ==========================================

                        let lastSeg = train.segments[train.segments.length - 1];
                        let destId = lastSeg.s[lastSeg.s.length - 1];
                        let destName = getStationName(destId);

                        let trainData = {
                            train: train,
                            trainNo: trainNo,
                            depTime: depT,
                            destName: destName,
                            diff: diff
                        };

                        if (isUpbound) upboundTrains.push(trainData);
                        else downboundTrains.push(trainData);

                        // 📝 登記：這台車已經加過了！
                        processedTrains.add(trainNo); 
                        
                        // 🌟 把你原本那行沒有宣告的 isAdded = true 刪掉了
                        break; // 跳出車站掃描的迴圈
                    }
                }
            }
        }
    });

    // 2. 依照發車時間排序
    upboundTrains.sort((a, b) => a.depTime - b.depTime);
    downboundTrains.sort((a, b) => a.depTime - b.depTime);

    // ==========================================
    // 🌟 1. 直接使用你原本系統就有的全域變數 isDarkMode！
    // ==========================================
    const theme = {
        cardBg: isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
        cardHoverBg: isDarkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.12)',
        textMain: isDarkMode ? '#FFFFFF' : '#222222',   // 淺色模式會變成深灰偏黑
        textSub: isDarkMode ? '#AAAAAA' : '#666666',    // 淺色模式會變成中灰色
        border: isDarkMode ? '#444444' : '#DDDDDD',
        timeGray: isDarkMode ? '#BBBBBB' : '#666666' 
    };

    // 🌟 2. 建立卡片 UI
    const buildRowHtml = (trains) => {
        if (trains.length === 0) {
            return `<div style="color: ${theme.textSub}; font-size: 13px; margin-left: 10px; font-style: italic;">近期無班次</div>`;
        }
        return trains.map(item => {
            
            // ==========================================
            // 🌟 3. 動態抓取對應的車種色碼
            // ==========================================
            let typeColors = settings?.train_color?.[item.train.type];
            let tColor = theme.textMain; 
            
            if (typeColors && typeColors.length > 0) {
                // 直接依據 isDarkMode 決定拿 [0] 還是 [1]
                tColor = isDarkMode ? typeColors[0] : (typeColors[1] || typeColors[0]);
            }
            
            let timeStr = formatTimeDisplay(item.depTime);
            let displayDiff = Math.floor(item.diff); 

            // 🌟 核心修改：卡片上的車種名稱也套用設定檔開關
            let displayTitle = (settings && settings.show_train_type === false) 
                ? item.trainNo 
                : `${item.train.type} ${item.trainNo}`;

            return `
                <div onclick="window.triggerSelectTrain('${item.trainNo}')" 
                     style="display: flex; flex-direction: column; justify-content: center; min-width: 120px; margin: 0 4px; padding: 4px 8px; background: ${theme.cardBg}; border-radius: 6px; cursor: pointer; border: 1px solid transparent; line-height: 1.2;"
                     onmouseover="this.style.background='${theme.cardHoverBg}'; this.style.borderColor='${tColor}'"
                     onmouseout="this.style.background='${theme.cardBg}'; this.style.borderColor='transparent'">
                    
                    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 2px;">
                        <span style="font-size: 15px; color: ${theme.textMain}; font-weight: bold;">${timeStr}</span>
                        <span style="font-size: 11px; color: ${tColor}; font-weight: bold;">${displayTitle}</span>
                    </div>
                    
                    <div style="display: flex; justify-content: space-between; align-items: baseline;">
                        <span style="font-size: 12px; color: ${theme.textSub};">往 ${item.destName}</span>
                        <span style="font-size: 11px; color: ${theme.timeGray}; font-weight: bold;">約 ${displayDiff} 分</span>
                    </div>

                </div>
            `;
        }).join('');
    };

    // 4. 組裝最終介面 (維持原樣)
    panel.innerHTML = `
        <div style="display: flex; width: 100%; height: 100%; align-items: center; color: ${theme.textMain};">
            <div style="min-width: 90px; display: flex; flex-direction: column; align-items: center; justify-content: center; padding-right: 15px; border-right: 1px solid ${theme.border}; flex-shrink: 0;">
                <div style="font-size: 20px; font-weight: bold;">${stName}</div>
                <div style="font-size: 12px; color: ${theme.textSub}; margin-top: 4px;">即將發車</div>
            </div>

            <div style="display: flex; flex-direction: column; justify-content: center; height: 100%; padding: 0 10px 0 15px; border-right: 1px solid ${theme.border}; flex-shrink: 0; gap: 10px;">
                <div style="color: #66B2FF; font-size: 13px; font-weight: bold; white-space: nowrap;">▲ 上行</div>
                <div style="color: #FF9999; font-size: 13px; font-weight: bold; white-space: nowrap;">▼ 下行</div>
            </div>

            <div id="bottom-scroll-container" style="flex: 1; display: flex; flex-direction: column; justify-content: center; height: 100%; overflow-x: auto; overflow-y: hidden; padding: 0 10px; scrollbar-width: none; gap: 4px;">
                <div style="display: flex; align-items: center;">
                    ${buildRowHtml(upboundTrains)}
                </div>
                <div style="display: flex; align-items: center;">
                    ${buildRowHtml(downboundTrains)}
                </div>
            </div>
        </div>
    `;
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
// 🎨 視覺優化濾鏡與時間校正
// ==========================================
function optimizeTrainTimesForDisplay(trainsData) {
    trainsData.forEach(train => {
        if (!train.segments) return;
        
        train.segments.forEach(seg => {
            // 🌟 1. 跨夜防呆：確保時間絕對不會「倒流」
            let lastT = seg.t[0];
            for (let i = 1; i < seg.t.length; i++) {
                // 如果時間突然往回掉 (例如 1435 分掉到 5 分)
                if (seg.t[i] < lastT && (lastT - seg.t[i]) > 300) { 
                    seg.t[i] += 1440; // 把隔天的時間強制加上 24 小時
                }
                lastT = Math.max(lastT, seg.t[i]); // 更新進度水位線
            }

            // 🌟 2. 撐開停靠站的水平線
            for (let i = 0; i < seg.t.length; i += 2) {
                // (順便修復一個小 Bug：v 的長度是 t 的一半，所以索引要是 i / 2)
                if (seg.t[i] === seg.t[i + 1] && seg.v[i / 2] !== 2) {
                    seg.t[i + 1] += 0.5; 
                }
            }
        });
    });
}

// ==========================================
// 🔄 跨面板互動觸發器：點擊火車自動置中版
// ==========================================
window.triggerSelectTrain = function(trainNo) {
    let targetTrain = timetable.find(t => (t.no === trainNo || t.train_no === trainNo));
    
    if (targetTrain) {
        // 🌟 1. 記住我們是從「哪個車站」點擊這班車的 (趁它被清空前趕快備份)
        let originStationId = selectedStation;

        // 2. 切換狀態：選中火車，清空車站面板，更新底部 UI
        selectedTrain = targetTrain;
        selectedStation = null;
        updateBottomPanel(selectedTrain);

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
        if (originStationId && targetMinutes !== null) {
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
// 🔄 跨面板互動觸發器 (終極驗屍官追蹤版)
// ==========================================
window.triggerSelectStation = function(st_id) {
    selectedStation = st_id;
    updateBottomPanelStation(selectedStation); 
    let stName = getStationName(st_id);

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
// 🌟 載入特定日期時刻表 (包含跨夜殘影合成技術)
// ==========================================
async function loadTimetableData(dateString) {
    try {
        let dirc_path = currentSystemPath + "json/"; 
        let formattedDate = dateString.replace(/-/g, ''); 
        
        // ------------------------------------------
        // 1. 載入「今天」的正班車時刻表
        // ------------------------------------------
        const timeRes = await fetch(`${dirc_path}timetable/timetable_${formattedDate}.json`);
        if (!timeRes.ok) throw new Error(`找不到檔案: timetable_${formattedDate}.json`);

        let todayData = await timeRes.json();
        interpolatePassingStations(todayData, topology);
        optimizeTrainTimesForDisplay(todayData);

        // ------------------------------------------
        // 2. 🌟 載入「昨天」的時刻表 (捕捉跨夜車殘影)
        // ------------------------------------------
        let yesterdayData = [];
        try {
            // 自動計算昨天的日期字串
            let dateObj = new Date(dateString);
            dateObj.setDate(dateObj.getDate() - 1); 
            let yyyy = dateObj.getFullYear();
            let mm = String(dateObj.getMonth() + 1).padStart(2, '0');
            let dd = String(dateObj.getDate()).padStart(2, '0');
            let yestFormatted = `${yyyy}${mm}${dd}`;

            const yestRes = await fetch(`${dirc_path}timetable/timetable_${yestFormatted}.json`);
            
            if (yestRes.ok) {
                let rawYesterday = await yestRes.json();
                interpolatePassingStations(rawYesterday, topology);
                optimizeTrainTimesForDisplay(rawYesterday); // 讓昨天的跨夜車時間先加上 1440

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
            console.log("無法載入昨天的資料，略過跨夜車呈現。");
        }

        // ------------------------------------------
        // 3. 雙劍合璧：將今天與昨天的跨夜殘影合併
        // ------------------------------------------
        timetable = todayData.concat(yesterdayData);

        currentDate = dateString; 

        // 大掃除
        selectedTrain = null;
        selectedStation = null;
        hoveredTrain = null;
        hoveredStation = null;
        updateBottomPanel(null);

        // 重新繪製新的一天的畫布
        redrawAll();

    } catch (e) {
        alert(`無法載入 ${dateString} 的時刻表！\n可能是該日期的資料尚未爬取。`);
        console.error(e);
    }
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

        globalData.countries.forEach(country => {
            // 建立國家標題
            const countryTitle = document.createElement('div');
            countryTitle.style.cssText = "width: 100%; color: #FFA500; font-size: 18px; margin-top: 20px; margin-bottom: 10px;";
            countryTitle.innerText = `📍 ${country.chinese_name}`;
            container.appendChild(countryTitle);

            // 建立該國家的系統按鈕
            country.systems.forEach(sys => {
                const btn = document.createElement('button');
                btn.className = 'pill-btn';
                
                // 🌟 核心修正：給按鈕一個身分證 ID，這樣 document 的監聽器才抓得到它
                btn.id = `btn-${sys.id}`; 
                
                if (sys.is_active) {
                    btn.innerText = sys.chinese_name;
                    btn.onclick = () => {
                        const dynamicPath = `data/${country.id}/${sys.id}/`;
                        
                        // 🌟 核心修正：進入前強制重置一次 Loader，確保它不會擋路
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
                    // 未開放的系統：反灰且不能點
                    btn.innerText = sys.chinese_name + " (建置中)";
                    btn.style.opacity = "0.4";
                    btn.style.cursor = "not-allowed";
                }
                
                container.appendChild(btn);
            });
        });
    } catch (e) {
        console.error("無法載入系統清單", e);
    }
}

// ==========================================
// 🌟 綁定「回到首頁」按鈕
// ==========================================
function bindHomeButton() {
    const btnHome = document.getElementById('btn-home');

    if (!btnHome || isHomeBound) return; // 🌟 如果綁過就直接退場
    isHomeBound = true;
    
    if (btnHome) {
        btnHome.addEventListener('click', () => {
            // 1. 停止背景的重繪計時器 (避免效能浪費與重疊 Bug)
            if (renderIntervalId) {
                clearInterval(renderIntervalId);
                renderIntervalId = null;
            }

            // 2. 清空畫布，避免下一次進來時看到殘影
            const canvas = document.getElementById('diaCanvas');
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // 3. 轉場動畫：隱藏主畫面，顯示首頁選單
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

    currentSystemPath = systemPath;

    try {
        
        let dirc_path = currentSystemPath + "json/"; // 確保路徑正確
        
        // 🌟 核心修正 2：所有的 fetch 都要加上 Cache Buster (?t=...)
        // 防止瀏覽器在切換系統時把「台鐵的檔案」當成「高鐵的檔案」餵給你
        const setRes = await fetch(`${dirc_path}setting.json?t=${Date.now()}`);
        if (!setRes.ok) throw new Error("找不到 setting.json");
        
        const settingText = await setRes.text();
        settings = JSON.parse(settingText);


        // 🌟 通用破解法：用正規表達式從純文字中挖出 train_color 的原始 Key 順序
        let extractedOrder = [];
        const colorBlockMatch = settingText.match(/"train_color"\s*:\s*\{([^}]*)\}/);
        if (colorBlockMatch) {
            // 抓出 block 裡所有的 "key":
            const keyMatches = [...colorBlockMatch[1].matchAll(/"([^"]+)"\s*:/g)];
            extractedOrder = keyMatches.map(m => m[1]);
        }
        // 將挖出來的原汁原味順序，掛載到 settings 物件上
        settings._rawOrder = extractedOrder;

        if (settings.system_name) {
            document.title = settings.system_name + " - 運行圖";
        }

        // 2. 載入 topology.json
        const topoRes = await fetch(dirc_path + 'topology.json');
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
        // 🌟 3. 判斷時刻表載入策略
        // ==========================================
        if (settings.data_fetch_strategy === "DAILY_FILE") {
            // 🌟 加上 ?t=${Date.now()} 確保每次抓到的都是該系統最新的日期
            const dateRes = await fetch(dirc_path + 'available_dates.json?t=' + Date.now());
            
            if (dateRes.ok) {
                availableDates = await dateRes.json();
            } else {
                console.warn("⚠️ 找不到 available_dates.json！");
                availableDates = ["2026-04-20"]; 
            }

            // 預設載入最後一天 (最新的一天)
            currentDate = availableDates[availableDates.length - 1];

            // ==========================================
            // 🌟 偵錯版：強制更新日曆並印出狀態
            // ==========================================

            // 🌟 這裡也同樣改用 getElementById
            const dateInput = document.getElementById('datePicker');

            if (dateInput) {

                // 2. 清空數值與摧毀實體
                dateInput.value = ""; 
                if (dateInput._flatpickr) {
                    dateInput._flatpickr.destroy();
                }

                // 3. 重新建立
                flatpickr(dateInput, {
                    defaultDate: currentDate,
                    enable: availableDates, 
                    dateFormat: "Y-m-d",
                    disableMobile: "true",
                    onChange: async function(selectedDates, dateStr, instance) {
                        await loadTimetableData(dateStr);
                    }
                });
            }


            // 啟動時先載入預設的第一張時刻表
            await loadTimetableData(currentDate);

        } else {
            // 模式 B：單一檔案模式 (維持你原本的寫法)
            const timeRes = await fetch(dirc_path + 'timetable/timetable_20260420.json');
            timetable = await timeRes.json();
            interpolatePassingStations(timetable, topology);
            optimizeTrainTimesForDisplay(timetable);
        }
        // ==========================================

        console.log("資料載入完成！建構 UI 與渲染畫布...");
        
        buildUI();         // 建立側邊欄按鈕
        updateBottomPanel(null); // 初始化底部面板
        bindThemeToggle(); // 啟動主題切換按鈕
        setupCanvasInteractions();
        setupBottomBarScrolling();

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

        // --- 🌟 核心新增：X 軸時間自動置中 ---
        const now = new Date();
        let currentMinutes = now.getHours() * 60 + now.getMinutes();
        
        // 鐵道標準跨夜處理：如果是凌晨 00:00 ~ 01:59，視為圖表上的 24:00 ~ 25:59
        if (currentMinutes < 120) {
            currentMinutes += 1440;
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