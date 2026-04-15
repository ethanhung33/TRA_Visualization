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
    scaleX: 2.5,     // X軸：1分鐘 = 2.5 pixels
    scaleY: 2.5,     // Y軸：1公里 = 2.5 pixels
    paddingTop: 50,  // 上方留白給時間標籤
    paddingLeft: 120 // 左側留白給車站名稱
};

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
            ctx.lineTo(CONFIG.paddingLeft + (1440 * CONFIG.scaleX), y);
            ctx.stroke();

            // --- 🌟 左右雙向懸浮站名 ---
            ctx.font = "bold 16px 'GlowSans', sans-serif";
            ctx.textBaseline = "middle";
            let maskBg = isDarkMode ? "rgba(0, 0, 0, 0.75)" : "rgba(255, 255, 255, 0.85)";
            let textColor = isDarkMode ? "#FFFFFF" : "#000000";
            let textWidth = ctx.measureText(st.name).width;

            // 左側站名
            let labelXLeft = Math.max(CONFIG.paddingLeft - 80, camera.x + 15);
            ctx.fillStyle = maskBg;
            ctx.fillRect(labelXLeft - 5, y - 12, textWidth + 10, 24);
            ctx.fillStyle = textColor;
            ctx.textAlign = "left";
            ctx.fillText(st.name, labelXLeft, y);

            // 右側站名
            let labelXRight = Math.min(CONFIG.paddingLeft + (1440 * CONFIG.scaleX) + 80, camera.x + canvas.width - 15);
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
    for (let m = 0; m <= 1440; m += 10) {
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
// 滑鼠互動：虛擬攝影機控制引擎 (無限縮放)
// ==========================================
function setupCanvasInteractions() {
    const wrapper = document.getElementById('canvas-wrapper');
    
    // 🌟 1. 關閉原生卷軸，由攝影機全面接管
    wrapper.style.position = 'relative';
    wrapper.style.overflow = 'hidden'; 
    wrapper.style.cursor = 'grab';

    let isDragging = false;
    let startMouseX, startMouseY, startCameraX, startCameraY;
    let renderFrame = null; 

    function checkInfiniteScroll() {
        let presetKey = currentRouteView + "_view"; 
        let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
        if (!isCircular) return; 

        // 判斷攝影機位置進行無縫傳送
        if (camera.y < loopHeight * 0.5) {
            camera.y += loopHeight; 
        } else if (camera.y > loopHeight * 1.5) {
            camera.y -= loopHeight; 
        }
    }

    // --- 拖曳事件 (平移攝影機) ---
    wrapper.addEventListener('mousedown', (e) => {
        isDragging = true;
        wrapper.style.cursor = 'grabbing';
        startMouseX = e.clientX;
        startMouseY = e.clientY;
        startCameraX = camera.x;
        startCameraY = camera.y;
    });

    wrapper.addEventListener('mouseleave', () => { isDragging = false; wrapper.style.cursor = 'grab'; });
    wrapper.addEventListener('mouseup', () => { isDragging = false; wrapper.style.cursor = 'grab'; });

    wrapper.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        e.preventDefault();
        
        // 🌟 2. 直接改變攝影機座標
        camera.x = startCameraX - (e.clientX - startMouseX);
        camera.y = startCameraY - (e.clientY - startMouseY);
        
        if (!renderFrame) {
            renderFrame = requestAnimationFrame(() => {
                checkInfiniteScroll();
                redrawAll();
                renderFrame = null;
            });
        }
    });

    // --- 滾輪事件 (加入滿版縮放限制) ---
    wrapper.addEventListener('wheel', (e) => {
        e.preventDefault();
        if (renderFrame) return;

        const rect = wrapper.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // 1. 先抓取目前的虛擬座標
        const virtualX = camera.x + mouseX;
        const virtualY = camera.y + mouseY;
        const dataX = (virtualX - CONFIG.paddingLeft) / CONFIG.scaleX;
        const dataY = (virtualY - CONFIG.paddingTop) / CONFIG.scaleY;

        // 2. 計算預計縮放後的新倍率
        const zoomSpeed = e.deltaY > 0 ? 0.9 : 1.1; 
        let newScaleX = CONFIG.scaleX * zoomSpeed;
        let newScaleY = CONFIG.scaleY * zoomSpeed;

        // 🌟 3. [核心限制邏輯] 確保縮小後不會小於螢幕
        const wrapperW = wrapper.clientWidth;
        const wrapperH = wrapper.clientHeight;

        // 橫軸：1440 分鐘縮放後的像素寬度
        const totalWidth = 1440 * newScaleX;
        if (totalWidth < wrapperW) {
            newScaleX = wrapperW / 1440; // 強制鎖定在滿版寬度
        }

        // 縱軸：一圈 (loopHeight) 縮放後的像素高度
        const totalHeight = loopKm * newScaleY;
        if (totalHeight < wrapperH) {
            newScaleY = wrapperH / loopKm; // 強制鎖定在滿版高度
        }

        // 額外的最大放大限制 (避免過大造成浮點數誤差)
        if (newScaleX > 150) newScaleX = 150;
        if (newScaleY > 150) newScaleY = 150;

        // 如果數值沒變（代表已經到極限了），就不需要重繪
        if (newScaleX === CONFIG.scaleX && newScaleY === CONFIG.scaleY) return;

        CONFIG.scaleX = newScaleX;
        CONFIG.scaleY = newScaleY;

        // 4. 重新對齊攝影機
        camera.x = (CONFIG.paddingLeft + dataX * newScaleX) - mouseX;
        camera.y = (CONFIG.paddingTop + dataY * newScaleY) - mouseY;

        renderFrame = requestAnimationFrame(() => {
            redrawAll();
            checkInfiniteScroll(); 
            renderFrame = null; 
        });

    }, { passive: false });
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
        redrawAll();       // 首次渲染畫布

        const wrapper = document.getElementById('canvas-wrapper');
        camera.y = loopHeight;

    } catch (e) {
        console.error("載入失敗:", e);
    }
}

init();