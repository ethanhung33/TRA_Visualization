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


// ==========================================
// 2. 核心換算函式
// ==========================================
function timeToX(minutes) {
    return CONFIG.paddingLeft + (minutes * CONFIG.scaleX);
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

    // 🌟 1. 整理唯一車站 (極簡自動接軌版)
    let uniqueStations = [];
    
    let lastStationId = null; // 🌟 記憶體：用來記住上一條路線的「最後一站」

    selectedSegments.forEach((segInput) => {
        let segId = typeof segInput === 'string' ? segInput : segInput.id;
        let seg = topology.segments.find(s => s.id === segId);
        if (!seg) return;

        // --- 處理截取 (維持原本的簡單邏輯) ---
        let stationsToDraw = [...seg.stations];
        if (typeof segInput === 'object') {
            let sIdx = 0, eIdx = seg.stations.length - 1;
            if (segInput.start) sIdx = seg.stations.findIndex(st => st.name === segInput.start || st.id === segInput.start);
            if (segInput.end) eIdx = seg.stations.findIndex(st => st.name === segInput.end || st.id === segInput.end);
            
            if (sIdx !== -1 && eIdx !== -1) {
                stationsToDraw = seg.stations.slice(Math.min(sIdx, eIdx), Math.max(sIdx, eIdx) + 1);
                if (sIdx > eIdx) stationsToDraw.reverse(); // 使用者手動指定的反轉
            }
        }
        if (stationsToDraw.length === 0) return;

        // ==========================================
        // 🌟 極簡魔法：自動判斷要不要反轉！
        // ==========================================
        if (lastStationId) {
            // 找找看上一條線的終點，在我這條線的哪個位置？
            let connectIdx = stationsToDraw.findIndex(st => st.id === lastStationId || st.name === lastStationId);
            
            // 如果找到了，而且「不是在第 0 個位置」 (代表它排在後面)，就整條線轉頭！
            if (connectIdx > 0) {
                stationsToDraw.reverse();
            }
        }
        // 記錄這條線畫完後的最後一站，交棒給下一條線去比對
        lastStationId = stationsToDraw[stationsToDraw.length - 1].id;
        // ==========================================

        // --- 下面繼續原本的畫格子與算里程邏輯 ---
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

    // 🌟 換成我們的高畫質工具！
    initCanvas('diaCanvas', 'canvas-wrapper');
    const wrapper = document.getElementById('canvas-wrapper'); // 保留這行因為後面程式可能會用到

    // 🌟 1. 新增這兩行：抓取「網頁邏輯尺寸」而不是放大的「物理尺寸」
    const wrapperW = wrapper.clientWidth;
    const wrapperH = wrapper.clientHeight;

    const viewTop = camera.y - 100;
    // 🌟 2. 下面這兩個把 canvas.height/width 換成 wrapperH/wrapperW
    const viewBottom = camera.y + wrapperH + 100; 
    const viewLeft = camera.x - 100;
    const viewRight = camera.x + wrapperW + 100;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(-camera.x, -camera.y);

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
                ? camera.y + canvas.height - 30 
                : Math.min(camera.y + canvas.height - 30, routeEndY + 30);

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
    // 🌟 新增：把「畫一台車」的邏輯打包起來
    // ==========================================
    // 🌟 在小括號裡面多加一個 isHovered 參數
    const drawSingleTrain = (train, isVIP, isHovered) => {
        // ==========================================
        // 🌟 1. 先決定這台車「原本的」顏色和粗細
        // ==========================================
        let baseColor = fallbackColor;
        if (settings && settings.train_color && settings.train_color[train.type]) {
            baseColor = settings.train_color[train.type][colorIndex];
        }

        let isExpress = ["新自強", "普悠瑪", "太魯閣", "自強", "莒光"].includes(train.type);
        let baseWidth = train.w || (isExpress ? 1.5 : 1.0);

        // 先把畫筆設定成預設狀態
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

                    if (seg.v[i] !== 2) ctx.lineTo(x_dep, y);
                    else ctx.moveTo(x_dep, y); 
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
        if (!activeTrainTypes.has(train.type)) return;

        if (train === selectedTrain) {
            vipTrain = train;
        } else if (train === hoveredTrain) {
            hoverTrainDraw = train;
        } else {
            // 畫普通車 (isVIP=false, isHovered=false)
            drawSingleTrain(train, false, false); 
        }
    });

    // 第二次：畫懸停的車 (壓在普通車上面)
    if (hoverTrainDraw) {
        drawSingleTrain(hoverTrainDraw, false, true); 
    }

    // 第三次：畫點擊的 VIP 車 (永遠壓在最上面)
    if (vipTrain) {
        drawSingleTrain(vipTrain, true, false); 
    }

    ctx.restore();
}

// ==========================================
// 🕒 繪製現在時間線 (跨夜影分身 + 智慧邊界版)
// ==========================================
function drawCurrentTimeLine() {
    const now = new Date();
    let currentMinutes = now.getHours() * 60 + now.getMinutes();

    const viewTop = camera.y;
    const viewBottom = camera.y + canvas.height;
    const viewLeft = camera.x;
    const viewRight = camera.x + canvas.width;

    // 🌟 新增邊界判斷
    let presetKey = currentRouteView + "_view"; 
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

    let timeCopies = [currentMinutes, currentMinutes + 1440];

    timeCopies.forEach(mins => {
        let x = timeToX(mins);

        if (x >= viewLeft && x <= viewRight) {
            ctx.beginPath();
            // 🌟 使用新的邊界畫紅線
            ctx.moveTo(x, lineTop);
            ctx.lineTo(x, lineBottom);
            ctx.stroke();

            // 讓紅線標籤也跟著智慧浮動
            let labelY = isCircular 
                ? Math.max(viewTop + 60, CONFIG.paddingTop) 
                : Math.max(lineTop + 40, Math.min(viewTop + 60, lineBottom - 20));
            
            ctx.fillText(now.getHours() + ":" + now.getMinutes().toString().padStart(2, '0'), x + 8, labelY);
        }
    });

    ctx.restore();
}

// ==========================================
// 5. UI 構建與事件綁定 (完美底色版)
// ==========================================

// ==========================================
// 🌟 終極防跳動換線處理 (修正錯位、閃爍與保持使用者縮放)
// ==========================================
function handleRouteSwitch(newRoute) {
    if (currentRouteView === newRoute) return;

    // --- 1. 記憶目前物理位置 (真實時間與里程) ---
    let anchorDataX = 0;
    let anchorDataY = 0;
    if (loopKm > 0) {
        anchorDataX = (camera.x - CONFIG.paddingLeft) / CONFIG.scaleX; // 記住 X 軸時間
        
        const currentLoopHeight = loopKm * CONFIG.scaleY;
        let relativeY = (camera.y - CONFIG.paddingTop) % currentLoopHeight;
        if (relativeY < 0) relativeY += currentLoopHeight;
        anchorDataY = relativeY / CONFIG.scaleY; // 記住 Y 軸里程
    }

    // --- 2. 切換狀態與 UI ---
    currentRouteView = newRoute;
    if (window.updateRouteButtons) window.updateRouteButtons();

    // --- 3. 背景偷偷計算新路線的總長度 (支援區間截取版) ---
    let newLoopKm = 0;
    let selectedSegments = settings?.view_presets?.[newRoute]?.lines || [];
    selectedSegments.forEach(segInput => {
        let segId = typeof segInput === 'string' ? segInput : segInput.id;
        let seg = topology.segments.find(s => s.id === segId);
        if (!seg) return;

        let stationsToDraw = seg.stations;
        if (typeof segInput === 'object') {
            let sIdx = 0;
            let eIdx = seg.stations.length - 1;
            if (segInput.start) sIdx = seg.stations.findIndex(st => st.name === segInput.start || st.id === segInput.start);
            if (segInput.end) eIdx = seg.stations.findIndex(st => st.name === segInput.end || st.id === segInput.end);
            
            if (sIdx !== -1 && eIdx !== -1) {
                let minIdx = Math.min(sIdx, eIdx);
                let maxIdx = Math.max(sIdx, eIdx);
                stationsToDraw = seg.stations.slice(minIdx, maxIdx + 1);
                
                // 🌟 這裡也同步反轉
                if (sIdx > eIdx) {
                    stationsToDraw.reverse();
                }
            }
        }

        if (stationsToDraw.length > 0) {
            let startKm = stationsToDraw[0].km;
            let endKm = stationsToDraw[stationsToDraw.length - 1].km;
            newLoopKm += Math.abs(endKm - startKm);
        }
    });
    
    loopKm = newLoopKm;

    // --- 4. 觸發防呆縮放 ---
    autoFitScale();

    // --- 5. 座標補償：精準降落回剛剛的時間與里程！ ---
    camera.x = Math.round(CONFIG.paddingLeft + (anchorDataX * CONFIG.scaleX));
    camera.y = Math.round(CONFIG.paddingTop + (anchorDataY * CONFIG.scaleY));

    // --- 6. 防禦性校正 ---
    if (loopKm > 0) loopHeight = loopKm * CONFIG.scaleY;
    checkInfiniteScroll();
    clampCamera();

    // --- 7. 安全重繪最終畫面 (只畫一次，拒絕錯位！) ---
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
    
    // 如果還沒有設定當前視角，預設選中 json 裡面的第一個！
    if (viewKeys.length > 0 && !currentRouteView) {
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

    // ---- B. 動態生成車種篩選按鈕 (同步 setting.json 順序) ----
    
    // 1. 抓出時刻表內實際有出現的車種集合
    const dataTypes = new Set(timetable.map(t => t.type));
    
    // 2. 優先依照 settings.train_color 定義的順序排隊
    let sortedTypes = [];
    if (settings && settings.train_color) {
        // 只留下時刻表裡確實有出現的車種，避免產生幽靈按鈕 (例如今天沒復興號就不顯示)
        sortedTypes = Object.keys(settings.train_color).filter(type => dataTypes.has(type));
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

    // 全選 
    btnAllTrains.addEventListener('click', () => {
        activeTrainTypes = new Set(sortedTypes);
        document.querySelectorAll('#train-type-container .pill-btn').forEach(b => { if(b._updateStyle) b._updateStyle(); });
        
        syncBottomPanel(); // 🌟 2. 全選時：同步更新面板！
        redrawAll();
    });

    // 全部不選
    btnNoTrains.addEventListener('click', () => {
        activeTrainTypes.clear();
        document.querySelectorAll('#train-type-container .pill-btn').forEach(b => { if(b._updateStyle) b._updateStyle(); });
        
        syncBottomPanel(); // 🌟 3. 全部不選時：同步更新面板！
        redrawAll();
    });
    
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
// 視窗大小改變處理 (Resize)
// ==========================================
let resizeTimeout;

window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    
    resizeTimeout = setTimeout(() => {
        const wrapper = document.getElementById('canvas-wrapper');
        if (!wrapper) return;

        // 🌟 1. 換成高畫質工具！
        initCanvas('diaCanvas', 'canvas-wrapper');

        // 2. 視窗改變後，螢幕寬度變了，必須強制校正邊界
        clampCamera(); 
        
        // 3. 重新畫圖
        redrawAll();
    }, 100); // 等使用者停止拉動視窗 100 毫秒後才執行
});

// 統整重繪動作 (清空 -> 畫網格 -> 畫火車)
function redrawAll() {
    // 由於我們動態改變 canvas.height，這本身就會清空畫布，
    // 但為保險起見還是加上 clearRect
    clampCamera();
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
            if (btn.id !== 'btn-mountain' && btn.id !== 'btn-sea' && !btn._updateStyle) {
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

        if (selectedStation) {
            updateBottomPanelStation(selectedStation);
        }
        else if (selectedTrain) {
            updateBottomPanel(selectedTrain);
        }

        // 4. 重繪畫布
        redrawAll();
    });
}

// ==========================================
// 🌟 視角自動適應 (徹底解放版：尊重 Y 軸完美貼合)
// ==========================================
function autoFitScale() {
    const wrapper = document.getElementById('canvas-wrapper');
    if (!wrapper || typeof loopKm === 'undefined' || loopKm <= 0) return;

    const minScaleY = (wrapper.clientHeight - 150) / loopKm;

    // 🌟 徹底解放：不再限制最大放大倍率！
    // 讓短路線能完美撐開上下邊界。X 軸變長沒關係，我們爽爽左右拖曳來看！
    if (CONFIG.scaleY < minScaleY) {
        CONFIG.scaleX = minScaleY;
        CONFIG.scaleY = minScaleY;
    }
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
// 設置畫布互動 (已修正 dataX 未定義與黑邊問題)
// ==========================================
function setupCanvasInteractions() {
    const wrapper = document.getElementById('canvas-wrapper');
    let isDragging = false;
    let startMouseX = 0, startMouseY = 0;
    let startCameraX = 0, startCameraY = 0;

    wrapper.addEventListener('mousedown', (e) => {
        isDragging = true;
        startMouseX = e.clientX; startMouseY = e.clientY;
        startCameraX = camera.x; startCameraY = camera.y;
        wrapper.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
        // 1. 如果正在按著滑鼠拖曳，就執行原本的地圖平移邏輯
        if (isDragging) {
            camera.x = startCameraX - (e.clientX - startMouseX);
            camera.y = startCameraY - (e.clientY - startMouseY);
            clampCamera(); // 拖曳校正
            requestRedraw();
            return; // 🌟 拖曳時不處理懸停變色，直接結束！
        }

        // 2. 如果沒有在拖曳，就啟動「懸停偵測」邏輯
        const rect = canvas.getBoundingClientRect();
        
        // 防呆：確保滑鼠真的在畫布範圍內
        if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) {
            if (hoveredTrain !== null || hoveredStation !== null) {
                hoveredTrain = null;
                hoveredStation = null;
                wrapper.style.cursor = 'grab';
                redrawAll();
            }
            return;
        }

        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        const worldX = mouseX + camera.x;
        const worldY = mouseY + camera.y;

        let closestTrain = null;
        let minDistance = 8; // 容錯距離 8 pixel

        // 🌟 沿著麵包屑尋找滑鼠下方的火車
        for (let train of timetable) { 
            if (!activeTrainTypes.has(train.type)) continue;
            if (!train._hitPoints) continue;

            for (let i = 0; i < train._hitPoints.length - 1; i++) {
                let p1 = train._hitPoints[i];
                let p2 = train._hitPoints[i+1];
                if (!p1 || !p2) continue;

                let dist = getDistanceToSegment(worldX, worldY, p1.x, p1.y, p2.x, p2.y);
                
                if (dist < minDistance) {
                    minDistance = dist;
                    closestTrain = train;
                }
            }
        }

        // ==========================================
        // 🌟 新增：尋找滑鼠下方的車站橫線 (優先度排在火車後面)
        // ==========================================
        let closestStationId = null;
        let minStationDist = 8; // Hover 的容錯距離 8px

        if (!closestTrain) { // 如果滑鼠沒有碰到火車，才去檢查有沒有碰到車站
            let presetKey = currentRouteView; 
            let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
            let copyStart = isCircular ? -1 : 0;
            let copyEnd = isCircular ? 1 : 0;

            for (let st_id in lookupY) {
                let opts = lookupY[st_id];
                for (let opt of opts) {
                    for (let copy = copyStart; copy <= copyEnd; copy++) {
                        // 🌟 把畫圖時的「偏移量」加回去算真實世界座標
                        let offsetY = isCircular ? ((copy * loopHeight) + CONFIG.paddingTop + loopHeight) : CONFIG.paddingTop;
                        let actualStationY = opt.y + offsetY;
                        let dy = Math.abs(worldY - actualStationY);

                        if (dy < minStationDist) {
                            minStationDist = dy;
                            closestStationId = st_id;
                        }
                    }
                }
            }
        }

        // ==========================================
        // 🌟 統整狀態改變與重繪邏輯
        // ==========================================
        let needsRedraw = false;

        if (hoveredTrain !== closestTrain) {
            hoveredTrain = closestTrain;
            needsRedraw = true;
        }

        if (hoveredStation !== closestStationId) {
            hoveredStation = closestStationId;
            needsRedraw = true;
        }

        // 只要火車或車站有狀態改變，就改變游標並重繪！
        if (needsRedraw) {
            wrapper.style.cursor = (hoveredTrain || hoveredStation) ? 'pointer' : 'grab';
            redrawAll(); 
        }
    });

    window.addEventListener('mouseup', (e) => {
        // 1. 恢復游標狀態
        wrapper.style.cursor = 'grab';

        // 2. 計算拖曳距離
        let dragDistance = Math.abs(e.clientX - startMouseX) + Math.abs(e.clientY - startMouseY);
        
        // 🌟 3. 判斷點擊！(此時 isDragging 還是 true 喔！)
        if (isDragging && dragDistance < 3) {
            const rect = canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            // 🌟 將滑鼠的「螢幕座標」加上鏡頭偏移，轉換成「世界座標」
            const worldX = mouseX + camera.x;
            const worldY = mouseY + camera.y;

            let closestTrain = null;
            let minDistance = 8; // 容錯距離 8 pixel

            // 🌟 沿著麵包屑尋找最近的火車！
            for (let train of timetable) { 
                if (!activeTrainTypes.has(train.type)) continue;
                if (!train._hitPoints) continue; // 如果沒有麵包屑就跳過

                // 兩兩一組，連成線段來計算滑鼠距離
                for (let i = 0; i < train._hitPoints.length - 1; i++) {
                    let p1 = train._hitPoints[i];
                    let p2 = train._hitPoints[i+1];

                    // 如果遇到 null (斷點)，這兩個點就不能連線，直接跳過
                    if (!p1 || !p2) continue;

                    // 計算距離 (因為麵包屑已經是世界座標了，直接算就好)
                    let dist = getDistanceToSegment(worldX, worldY, p1.x, p1.y, p2.x, p2.y);
                    
                    if (dist < minDistance) {
                        minDistance = dist;
                        closestTrain = train;
                    }
                }
            }
            
            if (closestTrain) {
                // 🌟 直接把這台車的物件存起來！
                selectedTrain = closestTrain; 
                selectedStation = null; // 點到火車就清空車站狀態
                updateBottomPanel(selectedTrain);
            } else {
                // ==========================================
                // 🌟 新增：如果沒點到火車，判斷有沒有點到車站橫線！
                // ==========================================
                let closestStationId = null;
                let minStationDist = 15; // Y軸容錯距離 15px

                // 取得現在的視圖狀態 (判斷是否為環島循環模式)
                let presetKey = currentRouteView; 
                let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
                let copyStart = isCircular ? -1 : 0;
                let copyEnd = isCircular ? 1 : 0;

                // 遍歷所有有畫在畫面上的車站 Y 座標
                for (let st_id in lookupY) {
                    let opts = lookupY[st_id];
                    
                    for (let opt of opts) {
                        // 🌟 關鍵修復 1：必須把畫圖時的「偏移量 (padding 與 圈數)」加回去！
                        for (let copy = copyStart; copy <= copyEnd; copy++) {
                            // 這行跟 drawGrid 裡面的 y 座標算式一模一樣
                            let offsetY = isCircular ? ((copy * loopHeight) + CONFIG.paddingTop + loopHeight) : CONFIG.paddingTop;
                            let actualStationY = opt.y + offsetY; // 這才是畫面上真正的那條線！
                            
                            // 計算滑鼠世界座標與真實線條的 Y 軸差距
                            let dy = Math.abs(worldY - actualStationY);
                            
                            // 🌟 關鍵修復 2：嚴格篩選「最小距離」！
                            if (dy < minStationDist) {
                                minStationDist = dy; 
                                closestStationId = st_id;
                            }
                        }
                    }
                }

                if (closestStationId) {
                    selectedStation = closestStationId;
                    selectedTrain = null; // 點到車站就清空火車狀態
                    updateBottomPanelStation(selectedStation); // 呼叫車站專屬面板
                } else {
                    // 點到空白處，全部清空
                    selectedTrain = null; 
                    selectedStation = null;
                    updateBottomPanel(null);
                }
            }
            redrawAll();
        }
        
        // 🌟 4. 最後的最後，才把 isDragging 關掉！
        isDragging = false;
    });

    wrapper.addEventListener('wheel', (e) => {
        e.preventDefault();
        if (renderFrame) return;

        const rect = wrapper.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        const wrapperW = wrapper.clientWidth;
        const wrapperH = wrapper.clientHeight;

        // 1. 抓取精確的物理座標
        const currentCamX = Math.round(camera.x);
        const currentCamY = Math.round(camera.y);

        // 🌟 2. 雙軸紀錄：精準記下「滑鼠游標正下方」的資料座標
        const dataX = (currentCamX + mouseX - CONFIG.paddingLeft) / CONFIG.scaleX;
        const dataY = (currentCamY + mouseY - CONFIG.paddingTop) / CONFIG.scaleY;

        // 3. 基礎縮放倍率
        let zoom = e.deltaY > 0 ? 0.9 : 1.1; 

        // 4. 計算"如果要把寬度或高度塞滿"所需要的最低倍率
        const minScaleX = (wrapperW - SIDE_MARGIN * 2) / 1560;
        const minScaleY = wrapperH / (loopKm || 1); 

        // 🌟 5. 終極等比例鎖定防護 (Aspect Ratio Lock)
        if (zoom < 1) { 
            const allowedZoomX = minScaleX / CONFIG.scaleX;
            const allowedZoomY = minScaleY / CONFIG.scaleY;

            let minAllowedZoom = Math.min(allowedZoomX, allowedZoomY);
            if (minAllowedZoom > 1) minAllowedZoom = 1;

            if (zoom < minAllowedZoom) {
                zoom = minAllowedZoom;
            }
        }

        if (zoom === 1 && e.deltaY > 0) return;

        // 6. 將同一個 zoom 完美且平等地套用到 X 和 Y！
        CONFIG.scaleX *= zoom;
        CONFIG.scaleY *= zoom;

        let targetX = (CONFIG.paddingLeft + dataX * CONFIG.scaleX) - mouseX;
        let targetY = (CONFIG.paddingTop + dataY * CONFIG.scaleY) - mouseY;

        // --- 6. X 軸邊界物理鎖定 ---
        const minLimitX = CONFIG.paddingLeft - SIDE_MARGIN;
        const contentWidth = 1560 * CONFIG.scaleX;
        const maxLimitX = CONFIG.paddingLeft + contentWidth - wrapperW + SIDE_MARGIN;

        if (contentWidth + (SIDE_MARGIN * 2) <= wrapperW + 1) {
            camera.x = minLimitX; 
        } else {
            camera.x = Math.max(minLimitX, Math.min(targetX, maxLimitX));
        }

        camera.y = targetY;

        // 8. 絕對像素鎖定
        camera.x = Math.round(camera.x);
        camera.y = Math.round(camera.y);

        // 🌟 9. 更新 loopHeight
        if (loopKm > 0) {
            loopHeight = loopKm * CONFIG.scaleY; 
        }

        checkInfiniteScroll();
        camera.y = Math.round(camera.y);

        requestRedraw();
    }, { passive: false });
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

// 將分鐘數轉換為 HH:MM 格式
function formatTimeDisplay(minutesRaw) {
    if (minutesRaw === undefined || minutesRaw === null) return "--:--";
    
    // 如果有跨夜 (超過 1440 分鐘)，可以選擇減掉或者保留 25:00 這種格式
    // 這裡我們示範標準 24 小時制 (如果有跨夜需求請自行拿掉 % 1440)
    let totalMinutes = Math.floor(minutesRaw) % 1440; 
    
    let hours = Math.floor(totalMinutes / 60);
    let mins = totalMinutes % 60;
    
    // 補零 (例如 8 -> 08)
    let hStr = hours.toString().padStart(2, '0');
    let mStr = mins.toString().padStart(2, '0');
    
    return `${hStr}:${mStr}`; // 配合你的截圖，回傳 "0815" 這種格式
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
            
            <div style="min-width: 150px; display: flex; align-items: center; padding-right: 20px; border-right: 2px solid #444; font-size: 32px; font-weight: 900; color: ${trainColor}; flex-shrink: 0; letter-spacing: 1px;">
                ${trainType} ${trainNo}
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
            let seg = train.segments[segIdx];

            for (let i = 0; i < seg.s.length; i++) {
                if (seg.s[i] === st_id && seg.v[i] !== 2 && seg.v[i] !== 3) {
                    let depT = seg.t[i * 2 + 1];
                    
                    // ==========================================
                    // 🌟 鐵道標準「營業日」時間轉換
                    // 將凌晨 00:00 ~ 01:59 視為當日的 24:00 ~ 25:59
                    // ==========================================
                    let opsNow = currentMinutes < 120 ? currentMinutes + 1440 : currentMinutes;
                    let opsDep = depT < 120 ? depT + 1440 : depT;
                    
                    // 重新計算最精準的倒數等待分鐘數
                    let diff = opsDep - opsNow;

                    // 🌟 只要這班車還沒開 (diff >= 0)，而且屬於今天收班前的車，就全部顯示！
                    if (diff >= 0 && opsDep >= opsNow) {
                        
                        // ==========================================
                        // 🌟 穿透雷達看方向 (只管大方向，不管下一站是誰)
                        // ==========================================
                        let isUpbound = true; 
                        let foundDirection = false;
                        let flatThreshold = 5; 

                        if (lookupY[st_id] && lookupY[st_id].length > 0) {
                            let currentY = lookupY[st_id][0].y;
                            
                            // 往未來的車站掃描，直到抓到明顯的 Y 軸變化
                            for (let sIdx = segIdx; sIdx < train.segments.length; sIdx++) {
                                let scanSeg = train.segments[sIdx];
                                let startIdx = (sIdx === segIdx) ? i + 1 : 0;

                                for (let k = startIdx; k < scanSeg.s.length; k++) {
                                    let scanStId = scanSeg.s[k];
                                    if (lookupY[scanStId] && lookupY[scanStId].length > 0) {
                                        let scanY = lookupY[scanStId][0].y;
                                        let dy = scanY - currentY;

                                        // 只要 Y 軸變化超過 5px，就判定大方向！
                                        if (Math.abs(dy) > flatThreshold) {
                                            isUpbound = (dy < 0); 
                                            foundDirection = true;
                                            break;
                                        }
                                    }
                                }
                                if (foundDirection) break; 
                            }
                        }

                        // 保底機制：如果都沒改變 Y 軸，退回奇偶數判斷
                        if (!foundDirection) {
                            isUpbound = (parseInt(trainNo) % 2 === 0);
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

                        processedTrains.add(trainNo);
                        isAdded = true;
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

            return `
                <div onclick="window.triggerSelectTrain('${item.trainNo}')" 
                     style="display: flex; flex-direction: column; justify-content: center; min-width: 120px; margin: 0 4px; padding: 4px 8px; background: ${theme.cardBg}; border-radius: 6px; cursor: pointer; border: 1px solid transparent; line-height: 1.2;"
                     onmouseover="this.style.background='${theme.cardHoverBg}'; this.style.borderColor='${tColor}'"
                     onmouseout="this.style.background='${theme.cardBg}'; this.style.borderColor='transparent'">
                    
                    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 2px;">
                        <span style="font-size: 15px; color: ${theme.textMain}; font-weight: bold;">${timeStr}</span>
                        <span style="font-size: 11px; color: ${tColor}; font-weight: bold;">${item.train.type} ${item.trainNo}</span>
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
// 🎨 視覺優化濾鏡：強制撐開同時間的停靠站
// ==========================================
function optimizeTrainTimesForDisplay(trainsData) {
    trainsData.forEach(train => {
        if (!train.segments) return;
        
        train.segments.forEach(seg => {
            // seg.t 裡面的資料格式是 [到站1, 離站1, 到站2, 離站2...]
            for (let i = 0; i < seg.t.length; i += 2) {
                if (seg.t[i] === seg.t[i + 1] && seg.v[i] !== 2) {
                    // 強制把離站時間往後延 1 分鐘 (為了讓 Canvas 畫出水平線)
                    seg.t[i + 1] += 0.5; 
                }
            }
        });
    });
}

// ==========================================
// 🔄 跨面板互動觸發器 (全域函數)
// ==========================================
window.triggerSelectTrain = function(trainNo) {
    let targetTrain = timetable.find(t => (t.no === trainNo || t.train_no === trainNo));
    if (targetTrain) {
        selectedTrain = targetTrain;
        selectedStation = null;
        updateBottomPanel(selectedTrain);
        redrawAll(); 
    }
};

// ==========================================
// 🔄 跨面板互動觸發器 (加入自動置中功能)
// ==========================================
window.triggerSelectStation = function(st_id) {
    selectedStation = st_id;
    selectedTrain = null;
    updateBottomPanelStation(selectedStation); // 呼叫車站面板

    // 🌟 新增：計算該車站的座標，並讓攝影機自動置中對準它！
    if (lookupY[st_id] && lookupY[st_id].length > 0) {
        
        // 1. 取得車站的基礎 Y 座標 (這是在 drawGrid 時算出來的純資料座標)
        let rawY = lookupY[st_id][0].y;
        
        // 2. 加上頂部 padding 轉換成真實的「畫布世界座標」
        let targetY = rawY + CONFIG.paddingTop;
        
        // --- (處理環島循環線的防呆判斷) ---
        let presetKey = currentRouteView; 
        let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
        
        if (isCircular && loopHeight > 0) {
            let currentCenterY = camera.y + (canvas.height / 2);
            let closestY = targetY;
            let minDist = Infinity;
            
            // 掃描上、中、下三圈，找出離目前視角最近的那條線
            for (let copy = -1; copy <= 1; copy++) {
                let actualY = rawY + ((copy * loopHeight) + CONFIG.paddingTop + loopHeight);
                let dist = Math.abs(actualY - currentCenterY);
                if (dist < minDist) {
                    minDist = dist;
                    closestY = actualY;
                }
            }
            targetY = closestY;
        }
        // ------------------------------------

        // 🌟 3. 核心運算：攝影機的 Y 點 = 目標物 Y 點 - (螢幕高度的一半)
        camera.y = targetY - (canvas.height / 2);
        
        // 4. 清除小數點，並確保鏡頭不會超出地圖邊界 (撞牆保護)
        camera.y = Math.round(camera.y);
        clampCamera(); 
    }

    redrawAll(); // 重繪畫布，讓畫面跳轉並畫上黃色選取線
};

// ==========================================
// 🌟 獨立出來的「載入特定日期時刻表」函式
// ==========================================
async function loadTimetableData(dateString) {
    try {
        let dirc_path = currentSystemPath + "json/"; // 確保路徑正確
        let formattedDate = dateString.replace(/-/g, ''); // 轉換格式: 2026-04-20 -> 20260420
        
        const timeRes = await fetch(`${dirc_path}timetable/timetable_${formattedDate}.json`);
        if (!timeRes.ok) throw new Error(`找不到檔案: timetable_${formattedDate}.json`);

        timetable = await timeRes.json();
        optimizeTrainTimesForDisplay(timetable);

        currentDate = dateString; // 成功載入後，更新當前日期狀態

        // 🌟 換日大掃除：清空畫面上點擊的車輛或車站
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
                btn.className = 'pill-btn'; // 套用你原本漂亮的膠囊按鈕樣式
                
                if (sys.is_active) {
                    btn.innerText = sys.chinese_name;
                    // 🌟 點擊事件：切換畫面並載入該系統！
                    btn.onclick = () => {
                        // 1. 拼出路徑 (例如: data/Taiwan/TRA/)
                        const dynamicPath = `data/${country.id}/${sys.id}/`;
                        
                        // 2. 轉場動畫：顯示 Loading，隱藏首頁，顯示主畫面
                        document.getElementById('loading-overlay').classList.remove('hidden');
                        document.getElementById('landing-page').style.display = 'none';
                        document.getElementById('app').style.display = 'flex';
                        
                        // 3. 呼叫 init()，並把路徑傳給它！
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

    // 1. 抓取螢幕的像素比 (一般螢幕是 1，Mac/手機通常是 2 或 3)
    const dpr = window.devicePixelRatio || 1;

    // 2. 抓取外層容器的實際 CSS 尺寸
    const displayWidth = wrapper.clientWidth;
    const displayHeight = wrapper.clientHeight;

    // 3. 把畫布的「真實像素」乘上像素比 (放大底層解析度)
    canvas.width = displayWidth * dpr;
    canvas.height = displayHeight * dpr;

    // 4. 把畫布的「顯示尺寸」強制縮回 CSS 尺寸 (看起來一樣大，但更密實)
    canvas.style.width = displayWidth + 'px';
    canvas.style.height = displayHeight + 'px';

    // 5. 將畫布的畫筆也等比例放大，這樣你原本寫的座標和字體大小都不用改！
    ctx.scale(dpr, dpr);

    return { canvas, ctx };
}

// ==========================================
// 系統啟動點 (init)
// ==========================================
async function init(systemPath) {

    currentSystemPath = systemPath;

    try {
        
        let dirc_path = currentSystemPath + "json/"; // 確保路徑正確
        
        // 1. 載入 setting.json
        const setRes = await fetch(dirc_path + 'setting.json');
        settings = await setRes.json();
        if (settings.system_name) {
            document.title = settings.system_name + " - 運行圖";
        }

        // 2. 載入 topology.json
        const topoRes = await fetch(dirc_path + 'topology.json');
        topology = await topoRes.json();

        // ==========================================
        // 🌟 3. 判斷時刻表載入策略
        // ==========================================
        if (settings.data_fetch_strategy === "DAILY_FILE") {
            const dateRes = await fetch(dirc_path + 'available_dates.json');
            
            if (dateRes.ok) {
                availableDates = await dateRes.json();
            } else {
                console.warn("⚠️ 找不到 available_dates.json！");
                availableDates = ["2026-04-20"]; 
            }

            // 預設載入最後一天 (最新的一天)
            currentDate = availableDates[availableDates.length - 1];

            // ==========================================
            // 🌟 升級版：使用 Flatpickr 綁定日曆
            // ==========================================
            const dateInput = document.querySelector('input[type="date"]'); 
            if (dateInput) {
                // Flatpickr 會自動接管這個 input
                flatpickr(dateInput, {
                    defaultDate: currentDate,
                    enable: availableDates, // 🌟 神級功能：直接把我們的清單餵給它，清單以外的日子全部自動反灰不能點！
                    dateFormat: "Y-m-d",
                    disableMobile: "true", // 強制手機版也用我們漂亮的日曆，不用原生的
                    onChange: async function(selectedDates, dateStr, instance) {
                        // 當使用者點擊合法的日期時，直接載入！不需要再 alert 防呆了！
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
        // 🌟 啟動時強制執行一次滿版校正 (取代原本的畫圖邏輯)
        // ==========================================
        redrawAll();      // 讓系統先算出預設路線的 loopKm (無論哪種模式都強制先算一次)
        autoFitScale();   // 算出最完美的拉伸比例
        camera.y = -50;   // 把畫面推到最頂端
        clampCamera();    // 確保不會超出邊界
        redrawAll();      // 畫出拉伸後的最終完美畫面！     

        // ==========================================
        // 🌟 5. 圖畫完了！把轉圈圈優雅地隱藏起來
        // ==========================================
        setTimeout(() => {
            const loader = document.getElementById('loading-overlay');
            if (loader) {
                loader.classList.add('hidden'); // 觸發 CSS 淡出動畫
            }
        }, 100); 

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