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
// 繪製背景網格 (結合 3圈架構 + 視圖剔除效能優化)
// ==========================================
function drawGrid(viewKey) {
    lookupY = {}; 
    let currentAccumulatedKm = 0; 
    let selectedSegments = VIEW_CONFIGS[viewKey];

    let presetKey = viewKey + "_view"; 
    let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";

    ctx.font = "12px 'Segoe UI', sans-serif";
    ctx.textBaseline = "middle";

    // 🌟 1. 取得目前螢幕的「真實可視範圍」 (加上 100px 的緩衝區，避免滑動邊緣閃爍)
    const wrapper = document.getElementById('canvas-wrapper');
    const viewTop = wrapper.scrollTop - 100;
    const viewBottom = wrapper.scrollTop + wrapper.clientHeight + 100;
    const viewLeft = wrapper.scrollLeft - 100;
    const viewRight = wrapper.scrollLeft + wrapper.clientWidth + 100;

    selectedSegments.forEach(segId => {
        let seg = topology.segments.find(s => s.id === segId);
        if (!seg) return;
        let segMaxKm = 0;
        seg.stations.forEach(st => {
            let absoluteKm = currentAccumulatedKm + st.km;
            lookupY[st.id] = absoluteKm * CONFIG.scaleY; 
            if (st.km > segMaxKm) segMaxKm = st.km;
        });
        currentAccumulatedKm += segMaxKm; 
    });

    loopKm = currentAccumulatedKm;
    loopHeight = loopKm * CONFIG.scaleY;

    // 限制畫布最大高度 (防白屏保護機制)
    const MAX_CANVAS_HEIGHT = 18000;
    let targetHeight = isCircular ? (loopHeight * 3) + (CONFIG.paddingTop * 2) : loopHeight + (CONFIG.paddingTop * 2);
    canvas.height = Math.min(targetHeight, MAX_CANVAS_HEIGHT);
    canvas.width = CONFIG.paddingLeft + (1440 * CONFIG.scaleX) + 100;

    let copyStart = isCircular ? -1 : 0;
    let copyEnd = isCircular ? 1 : 0;

    stationCoords = []; 

    for (let copy = copyStart; copy <= copyEnd; copy++) {
        let offsetY = isCircular ? ((copy * loopHeight) + CONFIG.paddingTop + loopHeight) : CONFIG.paddingTop;

        selectedSegments.forEach(segId => {
            let seg = topology.segments.find(s => s.id === segId);
            if (!seg) return;
            seg.stations.forEach(st => {
                let y = lookupY[st.id] + offsetY;
                
                if (copy === 0) stationCoords.push({ name: st.name, y: y }); 

                // 🌟 2. 垂直剔除 (Y軸)：如果這個車站在畫面外，直接跳過不畫！
                if (y < viewTop || y > viewBottom) return;

                // 畫橫線
                ctx.strokeStyle = isDarkMode ? "#333333" : "#E0E0E0";
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(CONFIG.paddingLeft, y);
                ctx.lineTo(CONFIG.paddingLeft + (1440 * CONFIG.scaleX), y);
                ctx.stroke();

                // 畫最左邊的實體站名
                ctx.fillStyle = isDarkMode ? "#AAAAAA" : "#333333";
                ctx.fillText(st.name, Math.max(20, viewLeft + 20), y); // 讓最左邊站名可以跟著畫面浮動

                // 🌟 3. 水平剔除 (X軸)：只畫出現在螢幕「左右範圍內」的浮水印
                ctx.fillStyle = isDarkMode ? "rgba(170, 170, 170, 0.25)" : "rgba(85, 85, 85, 0.35)";
                for (let h = 1; h < 24; h += 2) { 
                    let textX = timeToX(h * 60) + 5;
                    // 只有在可視範圍內的浮水印才執行 fillText
                    if (textX > viewLeft && textX < viewRight) {
                        ctx.fillText(st.name, textX, y - 8); 
                    }
                }
            });
        });
    }

    // 🌟 4. 時間垂直線也加入水平剔除
    for (let h = 0; h <= 24; h++) {
        let x = timeToX(h * 60);
        if (x < viewLeft || x > viewRight) continue; // 畫面外的時間線不畫

        ctx.beginPath();
        ctx.setLineDash([4, 4]); 
        ctx.strokeStyle = isDarkMode ? ((h % 1 === 0) ? "#555555" : "#222222") : ((h % 1 === 0) ? "#CCCCCC" : "#EEEEEE");
        ctx.lineWidth = 1;
        ctx.moveTo(x, Math.max(0, viewTop));                 
        ctx.lineTo(x, Math.min(canvas.height, viewBottom));     
        ctx.stroke();
        ctx.setLineDash([]); 
        
        ctx.fillStyle = isDarkMode ? "#888888" : "#666666";
        ctx.fillText(`${h}:00`, x - 15, Math.max(CONFIG.paddingTop - 15, viewTop + 15)); // 讓時間標籤跟著頂部浮動
    }
}

// ==========================================
// 繪製火車 (加入高速邊界剔除 Bounding Box Culling)
// ==========================================
function drawTrains() {
    // 🌟 1. 取得目前螢幕的真實範圍 (加點緩衝區確保線條不會突然斷掉)
    const wrapper = document.getElementById('canvas-wrapper');
    const viewTop = wrapper.scrollTop - 200;
    const viewBottom = wrapper.scrollTop + wrapper.clientHeight + 200;
    const viewLeft = wrapper.scrollLeft - 200;
    const viewRight = wrapper.scrollLeft + wrapper.clientWidth + 200;

    let presetKey = currentRouteView + "_view"; 
    let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
    let copyStart = isCircular ? -1 : 0;
    let copyEnd = isCircular ? 1 : 0;

    let colorIndex = isDarkMode ? 0 : 1;
    let fallbackColor = isDarkMode ? "#FFFFFF" : "#000000";

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

            // 預先計算解捲繞座標
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

            // 算出這台車在 X 軸的絕對極值 (首站時間到末站時間)
            let minX = timeToX(seg.t[0]);
            let maxX = timeToX(seg.t[seg.t.length - 1]);

            for (let copy = copyStart; copy <= copyEnd; copy++) {
                let offsetY = isCircular ? ((copy * loopHeight) + CONFIG.paddingTop + loopHeight) : CONFIG.paddingTop;
                
                // 🌟 2. 找出這段火車在這一圈的 Y 軸極值
                let minY = Infinity, maxY = -Infinity;
                for (let i = 0; i < unwrappedCoords.length; i++) {
                    if (unwrappedCoords[i] !== null) {
                        let y = unwrappedCoords[i] + offsetY;
                        if (y < minY) minY = y;
                        if (y > maxY) maxY = y;
                    }
                }

                // 🌟 3. 高速剔除 (如果整台車都在畫面外，直接跳過不畫！)
                if (maxX < viewLeft || minX > viewRight || maxY < viewTop || minY > viewBottom) {
                    continue; 
                }
                
                // 在畫面內才執行耗時的繪圖動作
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
// 滑鼠互動：拖曳、縮放 (修正硬體極限與防卡頓)
// ==========================================
function setupCanvasInteractions() {
    const wrapper = document.getElementById('canvas-wrapper');
    wrapper.style.position = 'relative';
    wrapper.style.cursor = 'grab';

    let isDragging = false;
    let startX, startY, scrollLeft, scrollTop;
    let renderFrame = null; 

    function checkInfiniteScroll() {
        let presetKey = currentRouteView + "_view"; 
        let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
        if (!isCircular) return; 

        if (wrapper.scrollTop < loopHeight * 0.5) {
            wrapper.scrollTop += loopHeight; 
        } else if (wrapper.scrollTop > loopHeight * 1.5) {
            wrapper.scrollTop -= loopHeight; 
        }
    }

    wrapper.addEventListener('mousedown', (e) => {
        isDragging = true;
        wrapper.style.cursor = 'grabbing';
        startX = e.pageX - wrapper.offsetLeft;
        startY = e.pageY - wrapper.offsetTop;
        scrollLeft = wrapper.scrollLeft;
        scrollTop = wrapper.scrollTop;
    });

    wrapper.addEventListener('mouseleave', () => { isDragging = false; wrapper.style.cursor = 'grab'; });
    wrapper.addEventListener('mouseup', () => { isDragging = false; wrapper.style.cursor = 'grab'; });

    wrapper.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        e.preventDefault();
        wrapper.scrollLeft = scrollLeft - (e.pageX - wrapper.offsetLeft - startX);
        wrapper.scrollTop = scrollTop - (e.pageY - wrapper.offsetTop - startY);
        
        // 拖曳時也要透過 rAF 來重繪，確保網格剔除能平滑跟上
        if (!renderFrame) {
            renderFrame = requestAnimationFrame(() => {
                redrawAll();
                checkInfiniteScroll();
                renderFrame = null;
            });
        }
    });

    wrapper.addEventListener('wheel', (e) => {
        e.preventDefault();
        if (renderFrame) return;

        const zoomSpeed = e.deltaY > 0 ? 0.9 : 1.1; 
        const newScaleX = CONFIG.scaleX * zoomSpeed;
        const newScaleY = CONFIG.scaleY * zoomSpeed;

        // 🌟 修正硬體極限：絕不允許畫布高度超過 15,000px (避開內顯的 16384 極限)
        const MAX_HARDWARE_LIMIT = 15000;
        let presetKey = currentRouteView + "_view"; 
        let isCircular = settings?.view_presets?.[presetKey]?.view_type === "CIRCULAR";
        let estimatedHeight = isCircular ? (loopKm * newScaleY * 3) : (loopKm * newScaleY);
        
        if (newScaleX < 0.5 || newScaleX > 25 || estimatedHeight > MAX_HARDWARE_LIMIT) {
            return; // 達到極限就停止放大，保護畫布不崩潰
        }

        const rect = wrapper.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const canvasX = wrapper.scrollLeft + mouseX;
        const canvasY = wrapper.scrollTop + mouseY;
        const dataX = (canvasX - CONFIG.paddingLeft) / CONFIG.scaleX;
        const dataY = (canvasY - CONFIG.paddingTop) / CONFIG.scaleY;

        CONFIG.scaleX = newScaleX;
        CONFIG.scaleY = newScaleY;

        renderFrame = requestAnimationFrame(() => {
            redrawAll();
            wrapper.scrollLeft = CONFIG.paddingLeft + (dataX * CONFIG.scaleX) - mouseX;
            wrapper.scrollTop = CONFIG.paddingTop + (dataY * CONFIG.scaleY) - mouseY;
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
        wrapper.scrollTop = loopHeight;

    } catch (e) {
        console.error("載入失敗:", e);
    }
}

init();