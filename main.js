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
// 繪製背景網格 (加入日/夜模式動態顏色)
// ==========================================
function drawGrid(viewKey) {
    lookupY = {}; 
    let currentAccumulatedKm = 0; 
    let selectedSegments = VIEW_CONFIGS[viewKey];

    ctx.font = "12px 'Segoe UI', sans-serif";
    ctx.textBaseline = "middle";

    selectedSegments.forEach(segId => {
        let seg = topology.segments.find(s => s.id === segId);
        if (!seg) return;

        let segMaxKm = 0;

        seg.stations.forEach(st => {
            let absoluteKm = currentAccumulatedKm + st.km;
            let y = CONFIG.paddingTop + (absoluteKm * CONFIG.scaleY);
            
            lookupY[st.id] = y;
            if (st.km > segMaxKm) segMaxKm = st.km;

            // 🌟 網格橫線：深色模式用深灰，淺色模式用淺灰
            ctx.strokeStyle = isDarkMode ? "#333333" : "#E0E0E0";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(CONFIG.paddingLeft, y);
            ctx.lineTo(CONFIG.paddingLeft + (1440 * CONFIG.scaleX), y);
            ctx.stroke();

            // 🌟 站名字體：深色模式用亮灰，淺色模式用深灰
            ctx.fillStyle = isDarkMode ? "#AAAAAA" : "#333333";
            ctx.fillText(st.name, 20, y);
        });

        currentAccumulatedKm += segMaxKm; 
    });

    canvas.height = CONFIG.paddingTop + (currentAccumulatedKm * CONFIG.scaleY) + 100;
    canvas.width = CONFIG.paddingLeft + (1440 * CONFIG.scaleX) + 100;

    // 畫時間垂直線
    for (let h = 0; h <= 24; h++) {
        let x = timeToX(h * 60);
        ctx.beginPath();
        
        ctx.setLineDash([4, 4]); 
        // 🌟 時間直線顏色動態切換
        if (isDarkMode) {
            ctx.strokeStyle = (h % 1 === 0) ? "#555555" : "#222222";
        } else {
            ctx.strokeStyle = (h % 1 === 0) ? "#CCCCCC" : "#EEEEEE";
        }
        
        ctx.lineWidth = 1;
        ctx.moveTo(x, CONFIG.paddingTop);
        ctx.lineTo(x, canvas.height - CONFIG.paddingTop);
        ctx.stroke();
        ctx.setLineDash([]); 
        
        ctx.fillStyle = isDarkMode ? "#888888" : "#666666";
        ctx.fillText(`${h}:00`, x - 15, CONFIG.paddingTop - 15);
    }
}

// ==========================================
// 繪製火車 (讀取 setting.json)
// ==========================================
function drawTrains() {
    // 決定要讀取陣列的第幾個顏色 (0:深色模式, 1:淺色模式)
    let colorIndex = isDarkMode ? 0 : 1;
    let fallbackColor = isDarkMode ? "#FFFFFF" : "#000000";

    timetable.forEach(train => {
        if (!activeTrainTypes.has(train.type)) return;

        // 🌟 從 settings 提取顏色，如果設定檔找不到這個車種，就用 fallbackColor
        let trainColor = fallbackColor;
        if (settings && settings.train_color && settings.train_color[train.type]) {
            trainColor = settings.train_color[train.type][colorIndex];
        }

        ctx.strokeStyle = trainColor; 
        
        // 判斷粗細：自強、普悠瑪、太魯閣等對號車加粗
        let isExpress = ["新自強", "普悠瑪", "太魯閣", "自強", "莒光"].includes(train.type);
        ctx.lineWidth = train.w || (isExpress ? 1.5 : 1.0);

        train.segments.forEach(seg => {
            ctx.beginPath();
            let isDrawing = false; 

            for (let i = 0; i < seg.s.length; i++) {
                let st_id = seg.s[i];
                let y = lookupY[st_id];
                
                if (y === undefined) {
                    isDrawing = false;
                    continue; 
                }

                let x_arr = timeToX(seg.t[i * 2]);
                let x_dep = timeToX(seg.t[i * 2 + 1]);

                if (!isDrawing) { ctx.moveTo(x_arr, y); isDrawing = true; } 
                else { ctx.lineTo(x_arr, y); }

                if (seg.v[i] !== 2) ctx.lineTo(x_dep, y);
            }
            ctx.stroke();
        });
    });
}
// ==========================================
// 5. UI 構建與事件綁定
// ==========================================
// ==========================================
// 5. UI 構建與事件綁定 (動態顏色版)
// ==========================================
function buildUI() {
    // ---- 取得當下主題色碼的輔助函數 ----
    function getColor(colorsArray) {
        if (!colorsArray) return isDarkMode ? "#555" : "#CCC";
        return isDarkMode ? colorsArray[0] : colorsArray[1];
    }

    // ---- A. 路線切換按鈕綁定 (吃 view_presets 顏色) ----
    const updateRouteButtons = () => {
        let mColor = getColor(settings?.view_presets?.mountain_view?.button_color);
        let sColor = getColor(settings?.view_presets?.sea_view?.button_color);

        if (currentRouteView === "mountain") {
            btnMountain.style.backgroundColor = mColor;
            btnMountain.style.borderColor = mColor;
            btnMountain.style.color = "#FFF";
            btnSea.style.backgroundColor = ""; btnSea.style.borderColor = ""; btnSea.style.color = "";
        } else {
            btnSea.style.backgroundColor = sColor;
            btnSea.style.borderColor = sColor;
            btnSea.style.color = "#FFF";
            btnMountain.style.backgroundColor = ""; btnMountain.style.borderColor = ""; btnMountain.style.color = "";
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

    // 初始化路線按鈕顏色
    updateRouteButtons();
    // 綁定到 window 讓主題切換時可以呼叫
    window.updateRouteButtons = updateRouteButtons; 

    // ---- B. 動態生成車種篩選按鈕 (吃 train_color 顏色) ----
    const types = [...new Set(timetable.map(t => t.type))];
    trainTypeContainer.innerHTML = ''; 
    
    types.forEach(type => {
        activeTrainTypes.add(type);

        const btn = document.createElement('button');
        btn.className = 'pill-btn';
        btn.textContent = type;
        
        // 🌟 定義這個按鈕專屬的顏色更新邏輯
        const updateTrainBtnStyle = () => {
            if (activeTrainTypes.has(type)) {
                let tColor = getColor(settings?.train_color?.[type]);
                btn.style.backgroundColor = tColor;
                btn.style.borderColor = tColor;
                btn.style.color = "#FFF";
            } else {
                // 未選取時，恢復 CSS 預設樣式 (透明底)
                btn.style.backgroundColor = "";
                btn.style.borderColor = "";
                btn.style.color = "";
            }
        };

        // 初始化套用顏色
        updateTrainBtnStyle();
        // 把函數存到 DOM 元素上，方便日夜切換時一次叫起來更新
        btn._updateStyle = updateTrainBtnStyle; 

        // 點擊事件
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
        
        // 切換背景顏色
        document.getElementById('canvas-wrapper').style.backgroundColor = isDarkMode ? "#000000" : "#FFFFFF";
        document.getElementById('sidebar').style.backgroundColor = isDarkMode ? "#333333" : "#F5F5F5";
        document.getElementById('sidebar').style.color = isDarkMode ? "#FFFFFF" : "#000000";
        document.querySelectorAll('.control-section h3').forEach(h3 => {
            h3.style.color = isDarkMode ? "#FFFFFF" : "#000000";
        });
        
        // 🌟 觸發所有按鈕重新讀取日/夜色碼
        if (window.updateRouteButtons) window.updateRouteButtons();
        document.querySelectorAll('#train-type-container .pill-btn').forEach(btn => {
            if(btn._updateStyle) btn._updateStyle();
        });
        
        redrawAll();
    });
}

// ==========================================
// 滑鼠互動：拖曳平移 (Pan) 與滾輪縮放 (Zoom)
// ==========================================
function setupCanvasInteractions() {
    const wrapper = document.getElementById('canvas-wrapper');
    
    // --- 變數：拖曳狀態 ---
    let isDragging = false;
    let startX, startY, scrollLeft, scrollTop;

    // 讓滑鼠在畫布上變成「手掌」圖示
    wrapper.style.cursor = 'grab';

    // ============================
    // 1. 滑鼠拖曳平移 (Pan)
    // ============================
    wrapper.addEventListener('mousedown', (e) => {
        isDragging = true;
        wrapper.style.cursor = 'grabbing'; // 抓取中的圖示
        // 紀錄按下的起始座標與當前卷軸位置
        startX = e.pageX - wrapper.offsetLeft;
        startY = e.pageY - wrapper.offsetTop;
        scrollLeft = wrapper.scrollLeft;
        scrollTop = wrapper.scrollTop;
    });

    wrapper.addEventListener('mouseleave', () => {
        isDragging = false;
        wrapper.style.cursor = 'grab';
    });

    wrapper.addEventListener('mouseup', () => {
        isDragging = false;
        wrapper.style.cursor = 'grab';
    });

    wrapper.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        e.preventDefault();
        // 計算滑鼠移動的距離
        const x = e.pageX - wrapper.offsetLeft;
        const y = e.pageY - wrapper.offsetTop;
        const walkX = (x - startX);
        const walkY = (y - startY);
        // 反向移動卷軸，營造出拖曳畫布的感覺
        wrapper.scrollLeft = scrollLeft - walkX;
        wrapper.scrollTop = scrollTop - walkY;
    });

    // ============================
    // 2. 滾輪縮放 (Zoom - 對齊滑鼠游標)
    // ============================
    wrapper.addEventListener('wheel', (e) => {
        e.preventDefault(); // 阻止網頁預設的上下捲動行為

        // 設定縮放速度與方向 (向上滾放大，向下滾縮小)
        const zoomSpeed = 0.1;
        const zoomDirection = e.deltaY > 0 ? -1 : 1; 
        const scaleMultiplier = 1 + (zoomDirection * zoomSpeed);

        // 預判新的比例尺，限制最大與最小縮放極限 (避免當機或看不見)
        const newScaleX = CONFIG.scaleX * scaleMultiplier;
        if (newScaleX < 0.5 || newScaleX > 15) return;

        // ---- 核心演算法：游標焦點對齊 ----
        // 步驟 A：取得滑鼠在 wrapper 視窗內的相對座標
        const rect = wrapper.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // 步驟 B：推算目前滑鼠指著的「實際數據值 (時間與里程)」
        // 扣除 padding 後再除以舊的比例尺
        const canvasX = wrapper.scrollLeft + mouseX;
        const canvasY = wrapper.scrollTop + mouseY;
        const dataX = (canvasX - CONFIG.paddingLeft) / CONFIG.scaleX;
        const dataY = (canvasY - CONFIG.paddingTop) / CONFIG.scaleY;

        // 步驟 C：更新全域比例尺
        CONFIG.scaleX = newScaleX;
        CONFIG.scaleY = CONFIG.scaleY * scaleMultiplier;

        // 步驟 D：觸發重新繪圖 (這會連帶改變 canvas.width 和 canvas.height)
        redrawAll();

        // 步驟 E：反推新的 Canvas 座標，並調整卷軸，確保滑鼠指著的地方不變
        const newCanvasX = CONFIG.paddingLeft + (dataX * CONFIG.scaleX);
        const newCanvasY = CONFIG.paddingTop + (dataY * CONFIG.scaleY);

        wrapper.scrollLeft = newCanvasX - mouseX;
        wrapper.scrollTop = newCanvasY - mouseY;

    }, { passive: false }); // 必須設為 false 才能使用 e.preventDefault()
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

    } catch (e) {
        console.error("載入失敗:", e);
    }
}

init();