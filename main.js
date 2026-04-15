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

// 渲染參數 (可根據螢幕大小自行微調)
const CONFIG = {
    scaleX: 2.5,     // X軸：1分鐘 = 2.5 pixels (拉寬一點比較好看)
    scaleY: 2.5,     // Y軸：1公里 = 2.5 pixels
    paddingTop: 50,
    paddingLeft: 120 // 留給站名的空間
};

// 資料狀態
let topology = null;
let timetable = [];
let lookupY = {}; 

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
// 3. 繪製背景網格 (動態拼接視角)
// ==========================================
function drawGrid(viewKey) {
    lookupY = {}; // 重置查詢表
    let currentAccumulatedKm = 0; 
    let selectedSegments = VIEW_CONFIGS[viewKey];

    // 暗色模式的字體設定
    ctx.font = "12px 'Segoe UI', sans-serif";
    ctx.textBaseline = "middle";

    selectedSegments.forEach(segId => {
        let seg = topology.segments.find(s => s.id === segId);
        if (!seg) return;

        let segMaxKm = 0;

        seg.stations.forEach(st => {
            // 🌟 將該站的相對里程，加上之前區段累積的里程，算出「絕對 Y 座標」
            let absoluteKm = currentAccumulatedKm + st.km;
            let y = CONFIG.paddingTop + (absoluteKm * CONFIG.scaleY);
            
            lookupY[st.id] = y;
            if (st.km > segMaxKm) segMaxKm = st.km;

            // 畫車站橫線 (暗色模式用深灰色)
            ctx.strokeStyle = "#333333";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(CONFIG.paddingLeft, y);
            ctx.lineTo(CONFIG.paddingLeft + (1440 * CONFIG.scaleX), y);
            ctx.stroke();

            // 畫站名 (淺灰色)
            ctx.fillStyle = "#AAAAAA";
            ctx.fillText(st.name, 20, y);
        });

        // 將這一段的總長度，加入累加器，給下一段當起點
        currentAccumulatedKm += segMaxKm; 
    });

    // 根據算出來的總長度，動態調整 Canvas 大小
    canvas.height = CONFIG.paddingTop + (currentAccumulatedKm * CONFIG.scaleY) + 100;
    canvas.width = CONFIG.paddingLeft + (1440 * CONFIG.scaleX) + 100;

    // 畫時間垂直線 (0:00 ~ 24:00)
    for (let h = 0; h <= 24; h++) {
        let x = timeToX(h * 60);
        ctx.beginPath();
        // 整點線畫稍微亮一點、粗一點
        ctx.strokeStyle = (h % 1 === 0) ? "#555555" : "#333333";
        ctx.lineWidth = (h % 1 === 0) ? 1.5 : 0.5;
        
        ctx.moveTo(x, CONFIG.paddingTop);
        ctx.lineTo(x, canvas.height - CONFIG.paddingTop);
        ctx.stroke();
        
        // 頂部時間標籤
        ctx.fillStyle = "#888888";
        ctx.fillText(`${h}:00`, x - 15, CONFIG.paddingTop - 15);
    }
}

// ==========================================
// 4. 繪製火車 (套用過濾器與視角)
// ==========================================
function drawTrains() {
    timetable.forEach(train => {
        // 🌟 1. 車種過濾：如果這班車的車種沒被勾選，直接跳過
        if (!activeTrainTypes.has(train.type)) return;

        // 🌟 2. 顏色設定：讀取 JSON 裡的 c 參數，若無則預設白色
        ctx.strokeStyle = train.c || "#FFFFFF"; 
        ctx.lineWidth = train.w || 1.2;

        train.segments.forEach(seg => {
            ctx.beginPath();
            let isDrawing = false; 

            for (let i = 0; i < seg.s.length; i++) {
                let st_id = seg.s[i];
                let y = lookupY[st_id];
                
                // 🌟 3. 視角過濾：如果現在是山線視角，海線車站會查不到 Y 座標，在此斷開連線
                if (y === undefined) {
                    isDrawing = false;
                    continue; 
                }

                let x_arr = timeToX(seg.t[i * 2]);
                let x_dep = timeToX(seg.t[i * 2 + 1]);
                let status = seg.v[i];

                if (!isDrawing) {
                    ctx.moveTo(x_arr, y); 
                    isDrawing = true;
                } else {
                    ctx.lineTo(x_arr, y); 
                }

                // 狀態 2 是 PASS，不用畫水平停靠線
                if (status !== 2) {
                    ctx.lineTo(x_dep, y);
                }
            }
            ctx.stroke();
        });
    });
}

// ==========================================
// 5. UI 構建與事件綁定
// ==========================================
function buildUI() {
    // ---- A. 路線切換按鈕綁定 ----
    btnMountain.addEventListener('click', () => {
        btnMountain.classList.add('active', 'green');
        btnSea.classList.remove('active', 'green');
        currentRouteView = "mountain";
        redrawAll();
    });

    btnSea.addEventListener('click', () => {
        btnSea.classList.add('active', 'green');
        btnMountain.classList.remove('active', 'green');
        currentRouteView = "sea";
        redrawAll();
    });

    // ---- B. 動態生成車種篩選按鈕 ----
    const types = [...new Set(timetable.map(t => t.type))];
    trainTypeContainer.innerHTML = ''; 
    
    types.forEach(type => {
        activeTrainTypes.add(type); // 預設全部啟用

        const btn = document.createElement('button');
        btn.className = 'pill-btn active blue';
        btn.textContent = type;
        
        // 單一按鈕點擊事件
        btn.addEventListener('click', () => {
            if (activeTrainTypes.has(type)) {
                activeTrainTypes.delete(type);
                btn.classList.remove('active', 'blue');
            } else {
                activeTrainTypes.add(type);
                btn.classList.add('active', 'blue');
            }
            redrawAll();
        });
        trainTypeContainer.appendChild(btn);
    });

    // 全選 / 全部不選
    btnAllTrains.addEventListener('click', () => {
        activeTrainTypes = new Set(types);
        document.querySelectorAll('#train-type-container .pill-btn').forEach(b => b.classList.add('active', 'blue'));
        redrawAll();
    });

    btnNoTrains.addEventListener('click', () => {
        activeTrainTypes.clear();
        document.querySelectorAll('#train-type-container .pill-btn').forEach(b => b.classList.remove('active', 'blue'));
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
// 6. 系統啟動點 (init)
// ==========================================
async function init() {
    console.log("正在載入 JSON 資料...");
    try {
        const topoRes = await fetch('topology.json');
        topology = await topoRes.json();

        const timeRes = await fetch('timetable.json');
        timetable = await timeRes.json();

        console.log("資料載入完成！建構 UI 與渲染畫布...");
        
        buildUI();    // 建立側邊欄按鈕
        redrawAll();  // 首次渲染畫布

    } catch (e) {
        console.error("載入失敗:", e);
        alert("資料載入失敗！請確認 topology.json 與 timetable.json 是否在同一目錄下，並使用 Local Server 開啟。");
    }
}

init();