// ==========================================
// 1. DOM 元素綁定與全域變數
// ==========================================
const canvas = document.getElementById('diaCanvas');
const ctx = canvas.getContext('2d');

// UI 控制項
const btnMountain = document.getElementById('btn-mountain');
const btnSea = document.getElementById('btn-sea');
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

// 🌟 還有這兩個主題狀態的變數也要確保有宣告到
let settings = null;        
let isDarkMode = true;      

// ... (往下繼續是你原本的程式碼) ...
// 視角與過濾狀態
let currentRouteView = "mountain"; 
let activeTrainTypes = new Set(); 


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
    let presetKey = viewKey + "_view"; 
    let selectedSegments = settings?.view_presets?.[presetKey]?.lines || [];
    let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";

    if (selectedSegments.length === 0) return; 

    // 🌟 1. 整理唯一車站 (線性模式下容許頭尾重複)
    let uniqueStations = [];
    selectedSegments.forEach(segId => {
        let seg = topology.segments.find(s => s.id === segId);
        if (!seg) return;
        let segMaxKm = 0;
        seg.stations.forEach(st => {
            let absoluteKm = currentAccumulatedKm + st.km;
            let yPos = absoluteKm * CONFIG.scaleY;

            // 🌟 將 lookupY 改為陣列，容納座標與對應的「路線 ID」
            if (!lookupY[st.id]) lookupY[st.id] = [];
            
            // 避免同一個交會站在同一條路線被存兩次
            let lastOpt = lookupY[st.id][lookupY[st.id].length - 1];
            if (!lastOpt || Math.abs(lastOpt.y - yPos) > 1.0) {
                lookupY[st.id].push({ y: yPos, segId: segId }); // 紀錄它是哪條線的座標
                uniqueStations.push({ id: st.id, name: st.name, baseY: yPos });
            }
            if (st.km > segMaxKm) segMaxKm = st.km;
        });
        currentAccumulatedKm += segMaxKm; 
    });

    loopKm = currentAccumulatedKm;
    loopHeight = loopKm * CONFIG.scaleY;

    // ... (底下的 canvas.width = wrapper.clientWidth... 等畫線邏輯皆維持不變)
    const wrapper = document.getElementById('canvas-wrapper');
    canvas.width = wrapper.clientWidth;
    canvas.height = wrapper.clientHeight;

    const viewTop = camera.y - 100;
    const viewBottom = camera.y + canvas.height + 100;
    const viewLeft = camera.x - 100;
    const viewRight = camera.x + canvas.width + 100;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(-camera.x, -camera.y);

    let copyStart = isCircular ? -1 : 0;
    let copyEnd = isCircular ? 1 : 0;

    for (let copy = copyStart; copy <= copyEnd; copy++) {
        let offsetY = isCircular ? ((copy * loopHeight) + CONFIG.paddingTop + loopHeight) : CONFIG.paddingTop;

        uniqueStations.forEach(st => {
            let y = st.baseY + offsetY;
            if (y < viewTop || y > viewBottom) return;

            // --- 畫背景橫線 ---
            ctx.strokeStyle = isDarkMode ? "#333333" : "#E0E0E0";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(CONFIG.paddingLeft, y);
            ctx.lineTo(CONFIG.paddingLeft + (1560 * CONFIG.scaleX), y);
            ctx.stroke();

            // --- 🌟 左右雙向懸浮站名 ---
            ctx.font = "bold 16px 'GlowSans', sans-serif";
            ctx.textBaseline = "middle";
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
            let labelXRight = Math.min(CONFIG.paddingLeft + (1560 * CONFIG.scaleX) + 50, camera.x + canvas.width - 10);
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

    // --- 🌟 上下雙向懸浮時間軸 ---
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
        ctx.moveTo(x, viewTop);                 
        ctx.lineTo(x, viewBottom);     
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

            // 頂部時間
            let labelYTop = Math.max(CONFIG.paddingTop - 25, camera.y + 30);
            ctx.fillStyle = maskBg;
            ctx.fillRect(x - textWidth/2 - 5, labelYTop - 15, textWidth + 10, 22);
            ctx.fillStyle = textColor;
            ctx.fillText(timeStr, x, labelYTop + 2);

            // 底部時間
            let labelYBottom = camera.y + canvas.height - 30;
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

    let presetKey = currentRouteView + "_view"; 
    let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
    let copyStart = isCircular ? -1 : 0;
    let copyEnd = isCircular ? 1 : 0;

    let colorIndex = isDarkMode ? 0 : 1;
    let fallbackColor = isDarkMode ? "#FFFFFF" : "#000000";

    ctx.save();
    ctx.translate(-camera.x, -camera.y);

    timetable.forEach(train => {
        if (!activeTrainTypes.has(train.type)) return;

        let trainColor = fallbackColor;
        if (settings && settings.train_color && settings.train_color[train.type]) {
            trainColor = settings.train_color[train.type][colorIndex];
        }

        ctx.strokeStyle = trainColor; 
        let isExpress = ["新自強", "普悠瑪", "太魯閣", "自強", "莒光"].includes(train.type);
        ctx.lineWidth = train.w || (isExpress ? 1.5 : 1.0);

        // 🌟 把記憶變數拉到「整班車」的層級
        let trainLastBaseY = null;
        let wrapOffset = 0; 

        train.segments.forEach((seg, segIdx) => {
            let unwrappedCoords = [];

            // --- A. 精準尋找座標 ---
            for (let i = 0; i < seg.s.length; i++) {
                let st_id = seg.s[i];
                let options = lookupY[st_id];
                if (!options || options.length === 0) { unwrappedCoords.push(null); continue; }

                // 🌟 終極精準選點：直接找尋「屬於當下路線段 (seg.id)」的座標
                let matchedOpt = options.find(opt => opt.segId === seg.id);
                
                // 防呆：如果找不到完全吻合的路線，再退回找距離最近的
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

            // --- B. 執行繪圖 ---
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

                for (let i = 0; i < seg.s.length; i++) {
                    let y_raw = unwrappedCoords[i];
                    if (y_raw === null) { isDrawing = false; continue; }

                    let y = y_raw + offsetY; 
                    let x_arr = timeToX(seg.t[i * 2]);
                    let x_dep = timeToX(seg.t[i * 2 + 1]);

                    // 乾淨俐落的連線，不再需要跳躍特判
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
            }
        });
    });

    ctx.restore();
}

// ==========================================
// 5. UI 構建與事件綁定 (完美底色版)
// ==========================================

// 🌟 終極防跳動換線處理 (修正無限捲動錯位問題)
function handleRouteSwitch(newRoute) {
    if (currentRouteView === newRoute) return; 

    // 1. 取得目前的總高度 (換線前的 loopHeight)
    const currentLoopHeight = loopKm * CONFIG.scaleY;

    // 🌟 2. 降維運算：把目前巨大的 Y 座標，強制轉換回「第 0 圈」的相對位置
    let relativeY = (camera.y - CONFIG.paddingTop) % currentLoopHeight;
    if (relativeY < 0) relativeY += currentLoopHeight; // 處理往上捲的負數情況

    // 記錄這個「絕對安全」的相對里程
    const anchorDataY = relativeY / CONFIG.scaleY;

    // 3. 切換路線狀態與 UI
    currentRouteView = newRoute;
    updateRouteButtons();

    // 🚨 4. 先執行你的資料更新 (很重要：這會讓 loopKm 更新為新路線的長度)
    // 假設你的 redrawAll 裡面會重新整理 uniqueStations 和 loopKm
    redrawAll();

    // 🌟 5. 座標補償：無視之前的圈數，把攝影機強制降落在「第 0 圈」的同一個位置
    camera.y = Math.round(CONFIG.paddingTop + (anchorDataY * CONFIG.scaleY));

    // 6. 防禦性檢查無限捲動
    checkInfiniteScroll();
    camera.y = Math.round(camera.y);
    
    // 7. 為了防閃爍，用 requestAnimationFrame 再畫一次最終結果
    requestAnimationFrame(redrawAll);
}

function buildUI() {
    // ---- 取得當下主題色碼的輔助函數 ----
    function getColor(colorsArray) {
        if (!colorsArray) return isDarkMode ? "#555" : "#CCC";
        return isDarkMode ? colorsArray[0] : colorsArray[1];
    }

    // ---- A. 路線切換按鈕綁定 ----
    const updateRouteButtons = () => {
        let mColor = getColor(settings?.view_presets?.mountain_view?.button_color);
        let sColor = getColor(settings?.view_presets?.sea_view?.button_color);

        // 🌟 定義未選取時的基礎底色 (深色模式用深灰，淺色模式用淺灰底黑字)
        let defaultBg = isDarkMode ? "#444444" : "#E0E0E0";
        let defaultBorder = isDarkMode ? "#555555" : "#CCCCCC";
        let defaultText = isDarkMode ? "#CCCCCC" : "#000000";

        // 🌟 定義彩色按鈕上面的字體顏色 (深色模式配黑字，淺色模式配白字)
        let selectedText = isDarkMode ? "#000000" : "#FFFFFF";

        // 判斷並上色
        if (currentRouteView === "mountain") {
            btnMountain.style.backgroundColor = mColor;
            btnMountain.style.borderColor = mColor;
            btnMountain.style.color = selectedText;
            
            btnSea.style.backgroundColor = defaultBg;
            btnSea.style.borderColor = defaultBorder;
            btnSea.style.color = defaultText;
        } else {
            btnSea.style.backgroundColor = sColor;
            btnSea.style.borderColor = sColor;
            btnSea.style.color = selectedText;

            btnMountain.style.backgroundColor = defaultBg;
            btnMountain.style.borderColor = defaultBorder;
            btnMountain.style.color = defaultText;
        }
    };

    // 🌟 綁定按鈕事件 (取代原本那兩大段)
    btnMountain.addEventListener('click', () => handleRouteSwitch("mountain"));
    btnSea.addEventListener('click', () => handleRouteSwitch("sea"));

    updateRouteButtons();
    window.updateRouteButtons = updateRouteButtons; 

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
    
    // 4. 使用排好序的 sortedTypes 來生成按鈕
    sortedTypes.forEach(type => {
        activeTrainTypes.add(type);

        const btn = document.createElement('button');
        btn.className = 'pill-btn';
        btn.textContent = type;
        
        // 🌟 車種按鈕的配色邏輯
        const updateTrainBtnStyle = () => {
            // 定義未選取時的基礎底色
            let defaultBg = isDarkMode ? "#444444" : "#E0E0E0";
            let defaultBorder = isDarkMode ? "#555555" : "#CCCCCC";
            let defaultText = isDarkMode ? "#CCCCCC" : "#000000";

            // 定義彩色按鈕上面的字體顏色
            let selectedText = isDarkMode ? "#000000" : "#FFFFFF";

            if (activeTrainTypes.has(type)) {
                // 有勾選：塗上 JSON 顏色 + 動態字體色
                let tColor = getColor(settings?.train_color?.[type]);
                btn.style.backgroundColor = tColor;
                btn.style.borderColor = tColor;
                btn.style.color = selectedText;
            } else {
                // 未勾選：套用對應主題的灰底
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
            redrawAll();
        });
        trainTypeContainer.appendChild(btn);
    });

    // 全選 / 全部不選 (這裡也要記得改成 sortedTypes)
    btnAllTrains.addEventListener('click', () => {
        activeTrainTypes = new Set(sortedTypes);
        document.querySelectorAll('#train-type-container .pill-btn').forEach(b => { if(b._updateStyle) b._updateStyle(); });
        redrawAll();
    });

    btnNoTrains.addEventListener('click', () => {
        activeTrainTypes.clear();
        document.querySelectorAll('#train-type-container .pill-btn').forEach(b => { if(b._updateStyle) b._updateStyle(); });
        redrawAll();
    });
    
    // ==========================================
    // 🌟 側邊欄收合功能綁定
    // ==========================================
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('sidebar-toggle');

    if (sidebar && toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            
            // 切換箭頭方向
            toggleBtn.textContent = sidebar.classList.contains('collapsed') ? '‹' : '›';

            // 等待動畫跑完 (0.3秒)，重新測量並放大畫布
            setTimeout(() => {
                const wrapper = document.getElementById('canvas-wrapper');
                if (wrapper) {
                    canvas.width = wrapper.clientWidth;  
                    canvas.height = wrapper.clientHeight;
                    clampCamera();
                    redrawAll();
                }
            }, 300); 
        });
    }
}

// ==========================================
// 視窗大小改變處理 (Resize)
// ==========================================
let resizeTimeout;

window.addEventListener('resize', () => {
    // 使用防抖動 (Debounce)：避免拖拉視窗時瘋狂重繪導致卡頓
    clearTimeout(resizeTimeout);
    
    resizeTimeout = setTimeout(() => {
        const wrapper = document.getElementById('canvas-wrapper');
        if (!wrapper) return;

        // 1. 重新設定 canvas 的「真實物理解析度」
        canvas.width = wrapper.clientWidth;
        canvas.height = wrapper.clientHeight;

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
}

// ==========================================
// 綁定主題切換功能
// ==========================================
// ==========================================
// 綁定主題切換功能
// ==========================================
function bindThemeToggle() {
    btnTheme.addEventListener('click', () => {
        isDarkMode = !isDarkMode;
        
        btnTheme.textContent = isDarkMode ? "🌞" : "🌙";

        // 🌟 核心新增：給 body 貼上/撕下 light-mode 標籤，讓 CSS 裡的毛玻璃按鈕變色！
        if (isDarkMode) {
            document.body.classList.remove('light-mode'); // 撕下標籤 (恢復深色模式)
        } else {
            document.body.classList.add('light-mode');    // 貼上標籤 (觸發淺色模式)
        }
        
        // 1. 切換畫布容器與側邊欄的背景顏色
        document.getElementById('canvas-wrapper').style.backgroundColor = isDarkMode ? "#000000" : "#FFFFFF";
        document.getElementById('sidebar').style.backgroundColor = isDarkMode ? "#333333" : "#F5F5F5";
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
        
        // 4. 重繪畫布
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
    let presetKey = currentRouteView + "_view"; 
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
    let presetKey = currentRouteView + "_view"; 
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
        if (!isDragging) return;
        camera.x = startCameraX - (e.clientX - startMouseX);
        camera.y = startCameraY - (e.clientY - startMouseY);
        clampCamera(); // 拖曳校正
        requestRedraw();
    });

    window.addEventListener('mouseup', () => {
        isDragging = false;
        wrapper.style.cursor = 'grab';
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
        if (zoom < 1) { // 只有在「縮小」時才需要防撞牆
            // 計算 X 和 Y 各自還能容忍多小的縮放倍率
            const allowedZoomX = minScaleX / CONFIG.scaleX;
            const allowedZoomY = minScaleY / CONFIG.scaleY;

            // 取比較「寬鬆」的極限 (Math.min)，這會允許畫面單邊留黑邊 (完美維持比例)
            let minAllowedZoom = Math.min(allowedZoomX, allowedZoomY);
            
            // 防止反彈：如果極限大於 1，代表畫面已經比螢幕小了，最多鎖死在 1 不准再縮
            if (minAllowedZoom > 1) minAllowedZoom = 1;

            // 撞牆判定：如果這次縮小的幅度超過了極限，就強制踩煞車
            if (zoom < minAllowedZoom) {
                zoom = minAllowedZoom;
            }
        }

        // 提前阻斷：如果已經縮到極限，且使用者還在往下滾，直接中斷以節省效能
        if (zoom === 1 && e.deltaY > 0) return;

        // 6. 將同一個 zoom 完美且平等地套用到 X 和 Y！(保證斜率絕對不變)
        CONFIG.scaleX *= zoom;
        CONFIG.scaleY *= zoom;

        // --- 下面接續你原本的 // 5. 雙軸對齊核心 ---
        let targetX = (CONFIG.paddingLeft + dataX * CONFIG.scaleX) - mouseX;
        // ... (保持不變) ...
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

        // --- 🌟 7. Y 軸直接套用跟隨，不加邊界鎖死 ---
        camera.y = targetY;

        // 8. 絕對像素鎖定
        camera.x = Math.round(camera.x);
        camera.y = Math.round(camera.y);

        // 🌟 9. [極度關鍵] 在檢查無限捲動前，強制更新 loopHeight！
        // 如果你不更新這個，縮放時 checkInfiniteScroll 會用舊高度算中心點，導致畫面向上暴衝！
        if (loopKm > 0) {
            // 請確認你原本是怎麼算 loopHeight 的，通常是這樣：
            loopHeight = loopKm * CONFIG.scaleY; 
        }

        // 10. 處理 Y 軸無限循環
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



// ==========================================
// 系統啟動點 (init)
// ==========================================
async function init() {
    try {
        let dirc_path = "data/Taiwan/TRA/json/";
        
        // 🌟 1. 多載入一個 setting.json
        const setRes = await fetch(dirc_path + 'setting.json');
        settings = await setRes.json();
        if (settings.system_name) {
            document.title = settings.system_name + " - 運行圖";
        }

        const topoRes = await fetch(dirc_path + 'topology.json');
        topology = await topoRes.json();

        const timeRes = await fetch(dirc_path + 'timetable/timetable_20260416.json');
        timetable = await timeRes.json();

        console.log("資料載入完成！建構 UI 與渲染畫布...");
        
        buildUI();         // 建立側邊欄按鈕
        bindThemeToggle(); // 🌟 啟動主題切換按鈕

        setupCanvasInteractions();

        // 🌟 1. 先偷偷畫一次，為了讓系統算出正確的 loopKm (總里程數)
        redrawAll();       

        // 🌟 2. 啟動 Auto Fit (自動計算完美比例)
        const wrapper = document.getElementById('canvas-wrapper');
        const minScaleX = (wrapper.clientWidth - SIDE_MARGIN * 2) / 1560;
        const minScaleY = wrapper.clientHeight / (loopKm || 1);

        // 將算出的完美比例覆寫回設定中
        CONFIG.scaleX = minScaleX; 
        CONFIG.scaleY = minScaleY; 

        // 更新比例後，重新計算正確的像素總高度
        loopHeight = loopKm * CONFIG.scaleY;

        // 🌟 3. 依據不同模式決定初始攝影機降落點
        let presetKey = currentRouteView + "_view"; 
        let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
        
        if (isCircular) {
            camera.y = loopHeight; // 環狀模式看中間圈
        } else {
            camera.y = -50;        // 線性模式貼齊上方
        }
        
        // 🌟 4. 最終邊界校正與完美渲染
        clampCamera(); 
        redrawAll();   

    } catch (e) {
        console.error("載入失敗:", e);
    }
}

init();