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

let camera = { x: 0, y: 0 };

let stationCoords = [];

// 🌟 還有這兩個主題狀態的變數也要確保有宣告到
let settings = null;        
let isDarkMode = true;      

// ... (往下繼續是你原本的程式碼) ...
// 視角與過濾狀態
let currentRouteView = "mountain"; 
let activeTrainTypes = new Set(); 



// 定義不同視角需要拼接的區段 (這對應 topology.json 裡的 segment_id)
const VIEW_CONFIGS = {
    "mountain": ["north_main", "mountain_line", "south_main", "eastern_trunk"],
    "sea":      ["north_main", "sea_line",      "south_main", "eastern_trunk"]
};

// ==========================================
// 2. 核心換算函式
// ==========================================
function timeToX(minutes) {
    return CONFIG.paddingLeft + (minutes * CONFIG.scaleX);
}


// ==========================================
// 繪製背景網格 (純淨重置版 + 照妖鏡)
// ==========================================
function drawGrid(viewKey) {
    lookupY = {}; 
    let currentAccumulatedKm = 0; 
    let selectedSegments = VIEW_CONFIGS[viewKey];
    let presetKey = viewKey + "_view"; 
    let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";

    // 1. 整理唯一車站
    let uniqueStations = [];
    let seenIds = new Set();
    selectedSegments.forEach(segId => {
        let seg = topology.segments.find(s => s.id === segId);
        if (!seg) return;
        let segMaxKm = 0;
        seg.stations.forEach(st => {
            let absoluteKm = currentAccumulatedKm + st.km;
            if (!seenIds.has(st.id)) {
                lookupY[st.id] = absoluteKm * CONFIG.scaleY;
                seenIds.add(st.id);
                uniqueStations.push({ id: st.id, name: st.name, baseY: lookupY[st.id] });
            }
            if (st.km > segMaxKm) segMaxKm = st.km;
        });
        currentAccumulatedKm += segMaxKm; 
    });

    loopKm = currentAccumulatedKm;
    loopHeight = loopKm * CONFIG.scaleY;

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

// ==========================================
// 繪製火車 (加入高速邊界剔除 Bounding Box Culling)
// ==========================================
function drawTrains() {
    const wrapper = document.getElementById('canvas-wrapper');
    // 取得攝影機範圍
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

    // 🌟 套用攝影機偏移
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

        train.segments.forEach(seg => {
            let unwrappedCoords = [];
            let lastBaseY = null;
            let wrapOffset = 0; 

            for (let i = 0; i < seg.s.length; i++) {
                let st_id = seg.s[i];
                let baseY = lookupY[st_id];
                if (baseY === undefined) { unwrappedCoords.push(null); continue; }

                if (lastBaseY !== null && isCircular) {
                    let dy = baseY - lastBaseY;
                    if (dy > loopHeight / 2) wrapOffset -= loopHeight; 
                    else if (dy < -loopHeight / 2) wrapOffset += loopHeight; 
                }
                unwrappedCoords.push(baseY + wrapOffset);
                lastBaseY = baseY;
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

                // 高速邊界剔除
                if (maxX < viewLeft || minX > viewRight || maxY < viewTop || minY > viewBottom) {
                    continue; 
                }
                
                ctx.beginPath();
                let isDrawing = false; 

                for (let i = 0; i < seg.s.length; i++) {
                    let y_raw = unwrappedCoords[i];
                    if (y_raw === null) { isDrawing = false; continue; }

                    let y = y_raw + offsetY; 
                    let x_arr = timeToX(seg.t[i * 2]);
                    let x_dep = timeToX(seg.t[i * 2 + 1]);

                    if (!isDrawing) { ctx.moveTo(x_arr, y); isDrawing = true; } 
                    else { ctx.lineTo(x_arr, y); }

                    if (seg.v[i] !== 2) ctx.lineTo(x_dep, y);
                }
                ctx.stroke();
            }
        });
    });

    ctx.restore(); // 畫完復原
}

// ==========================================
// 5. UI 構建與事件綁定 (完美底色版)
// ==========================================
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

    btnMountain.addEventListener('click', () => {
        currentRouteView = "mountain";
        updateRouteButtons();
        redrawAll();
    });

    btnSea.addEventListener('click', () => {
        currentRouteView = "sea";
        updateRouteButtons();
        redrawAll();
    });

    updateRouteButtons();
    window.updateRouteButtons = updateRouteButtons; 

    // ---- B. 動態生成車種篩選按鈕 ----
    const types = [...new Set(timetable.map(t => t.type))];
    trainTypeContainer.innerHTML = ''; 
    
    types.forEach(type => {
        activeTrainTypes.add(type);

        const btn = document.createElement('button');
        btn.className = 'pill-btn';
        btn.textContent = type;
        
        // 🌟 車種按鈕的邏輯也一模一樣
        // 🌟 車種按鈕的邏輯
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

    // 全選 / 全部不選
    btnAllTrains.addEventListener('click', () => {
        activeTrainTypes = new Set(types);
        document.querySelectorAll('#train-type-container .pill-btn').forEach(b => { if(b._updateStyle) b._updateStyle(); });
        redrawAll();
    });

    btnNoTrains.addEventListener('click', () => {
        activeTrainTypes.clear();
        document.querySelectorAll('#train-type-container .pill-btn').forEach(b => { if(b._updateStyle) b._updateStyle(); });
        redrawAll();
    });
}

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
// 核心限制函數：禁止攝影機滑出邊界
// ==========================================
function clampCamera() {
    const wrapper = document.getElementById('canvas-wrapper');
    if (!wrapper) return;
    const wrapperW = wrapper.clientWidth;

    // 計算目前的總地圖寬度
    const contentWidth = TOTAL_MINUTES * CONFIG.scaleX;
    
    // 左邊界極限：讓 0:00 距離螢幕左緣固定為 SIDE_MARGIN
    const minX = CONFIG.paddingLeft - SIDE_MARGIN;
    
    // 右邊界極限：地圖尾端距離螢幕右緣固定為 SIDE_MARGIN
    const maxX = CONFIG.paddingLeft + contentWidth - wrapperW + SIDE_MARGIN;

    // 🌟 邏輯：如果地圖寬度 + 兩邊留白 < 螢幕寬度，則強制鎖死在 minX，不准置中
    if (contentWidth + (SIDE_MARGIN * 2) <= wrapperW + 1) { // +1 是為了防止浮點數誤差
        camera.x = minX;
    } else {
        // 只有在地圖比螢幕寬時，才允許在 minX 與 maxX 之間滑動
        if (camera.x < minX) camera.x = minX;
        if (camera.x > maxX) camera.x = maxX;
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

        // 1. 🌟 [核心 1] 抓取目前「正確且取整」的攝影機位置 (避免累積浮點數誤差)
        const currentCamX = Math.round(camera.x);
        const currentCamY = camera.y;

        // 2. 計算目前滑鼠指在地圖上的哪個資料點 (資料座標 DataX)
        const dataX = (currentCamX + mouseX - CONFIG.paddingLeft) / CONFIG.scaleX;
        const dataY = (currentCamY + mouseY - CONFIG.paddingTop) / CONFIG.scaleY;

        // 3. 計算新倍率
        const zoomSpeed = e.deltaY > 0 ? 0.9 : 1.1; // 滾輪下為縮小，上為放大
        let nextScaleX = CONFIG.scaleX * zoomSpeed;
        let nextScaleY = CONFIG.scaleY * zoomSpeed;

        // --- 🌟 [核心 2] 最小比例限制 (改用 1560) ---
        const wrapperW = wrapper.clientWidth;
        // 確保地圖最小寬度 + SIDE_MARGIN*2 = 螢幕寬度
        const minScaleX = (wrapperW - SIDE_MARGIN * 2) / 1560;
        
        // 這裡就是「防抖動」的關鍵：防止在最小比例上下微小跳動
        if (nextScaleX < minScaleX + 0.000001) nextScaleX = minScaleX; 

        // 更新高度比例限制 ( loopKm || 1 避免資料載入中的 0 )
        const wrapperH = wrapper.clientHeight;
        const minScaleY = wrapperH / (loopKm || 1); 
        if (nextScaleY < minScaleY) nextScaleY = minScaleY;

        // 套用新倍率
        CONFIG.scaleX = nextScaleX;
        CONFIG.scaleY = nextScaleY;

        // --- 🌟 [核心 3] 原子化座標補償 (消除跳動的核心) ---
        // 計算縮放後的物理邊界極限
        const minLimitX = CONFIG.paddingLeft - SIDE_MARGIN; // 左邊界撞牆點
        const contentWidth = 1560 * CONFIG.scaleX; // 縮放後的總內容像素寬度
        const maxLimitX = CONFIG.paddingLeft + contentWidth - wrapperW + SIDE_MARGIN; // 右邊界撞牆點

        // 先計算「理想中」為了對齊滑鼠需要的攝影機位置
        let targetX = (CONFIG.paddingLeft + dataX * CONFIG.scaleX) - mouseX;

        // 這裡就是「防跳動」的物理鎖定邏輯：
        if (contentWidth + (SIDE_MARGIN * 2) <= wrapperW + 1) {
            // [情況 A] 縮得太小：內容寬度小於螢幕，鎖死靠左
            camera.x = minLimitX; 
        } else {
            // [情況 B] 畫面夠寬：
            // 我們把「理想座標」嚴格「夾緊」在 minLimitX 和 maxLimitX 之間。
            // 這樣在放大瞬間，公式雖然想跳，但 `Math.min/max` 會瞬間把它按在邊界上，
            // 畫面就會呈現「平滑滾動到邊緣停住」，而不是「跳動」。
            camera.x = Math.max(minLimitX, Math.min(targetX, maxLimitX));
        }

        camera.x = Math.round(camera.x); 
        camera.y = Math.round(camera.y);
        
        checkInfiniteScroll(); // 垂直循環校正

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

// 🌟 新增這個函數，並在 mousemove 和 wheel 結尾呼叫它
function clampCamera() {
    const wrapper = document.getElementById('canvas-wrapper');
    if (!wrapper) return;
    const wrapperW = wrapper.clientWidth;

    // 🌟 1. 定義「理想中」左邊 0:00 線應該待的位置
    // 座標計算：camera.x = 內容起點 - 想要的螢幕偏移
    const minX = CONFIG.paddingLeft - SIDE_MARGIN;
    
    // 🌟 2. 計算右邊界極限
    const contentWidth = 1560 * CONFIG.scaleX;
    const maxX = CONFIG.paddingLeft + contentWidth - wrapperW + SIDE_MARGIN;

    // 🌟 3. 核心邏輯修正
    if (contentWidth + (SIDE_MARGIN * 2) < wrapperW) {
        // [情況 A]：如果地圖縮得太小，寬度比螢幕還窄
        // 我們不再強制居中，而是強制讓它「距離左邊 SIDE_MARGIN」
        camera.x = minX; 
    } else {
        // [情況 B]：地圖比螢幕寬，這時才執行「撞牆限制」
        if (camera.x < minX) camera.x = minX;
        if (camera.x > maxX) camera.x = maxX;
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

        const topoRes = await fetch(dirc_path + 'topology.json');
        topology = await topoRes.json();

        const timeRes = await fetch(dirc_path + 'timetable/timetable_20260415.json');
        timetable = await timeRes.json();

        console.log("資料載入完成！建構 UI 與渲染畫布...");
        
        buildUI();         // 建立側邊欄按鈕
        bindThemeToggle(); // 🌟 啟動主題切換按鈕

        setupCanvasInteractions();
        clampCamera();
        redrawAll();       // 首次渲染畫布

        const wrapper = document.getElementById('canvas-wrapper');
        camera.y = loopHeight;

    } catch (e) {
        console.error("載入失敗:", e);
    }
}

init();