const canvas = document.getElementById('diaCanvas');
const ctx = canvas.getContext('2d');
const routeSelect = document.getElementById('routeSelect');

const CONFIG = {
    scaleX: 2,       
    scaleY: 2,       
    paddingTop: 50,
    paddingLeft: 100 
};

let topology = null;
let timetable = [];
let lookupY = {}; 

// 🌟 定義視角的區段組合
const VIEW_CONFIGS = {
    "mountain": ["north_main", "mountain_line", "south_main"],
    "sea":      ["north_main", "sea_line", "south_main"]
};

function timeToX(minutes) {
    return CONFIG.paddingLeft + (minutes * CONFIG.scaleX);
}

// ==========================================
// 動態網格繪製 (根據選擇的視角拼接 Y 軸)
// ==========================================
function drawGrid(viewKey) {
    // 每次重畫都要清空查詢表
    lookupY = {}; 
    let currentAccumulatedKm = 0; 
    let selectedSegments = VIEW_CONFIGS[viewKey];

    ctx.font = "12px sans-serif";
    ctx.textBaseline = "middle";

    selectedSegments.forEach(segId => {
        // 從 topology 找出對應的區段
        let seg = topology.segments.find(s => s.id === segId);
        if (!seg) return;

        let segMaxKm = 0;

        seg.stations.forEach(st => {
            // 🌟 核心：畫布的絕對 Y 座標 = (之前區段累積的里程 + 這一站的段內里程) * 比例尺
            let absoluteKm = currentAccumulatedKm + st.km;
            let y = CONFIG.paddingTop + (absoluteKm * CONFIG.scaleY);
            
            // 寫入查詢表
            lookupY[st.id] = y;
            if (st.km > segMaxKm) segMaxKm = st.km;

            // 畫車站橫線
            ctx.strokeStyle = "#eeeeee";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(CONFIG.paddingLeft, y);
            ctx.lineTo(CONFIG.paddingLeft + (1440 * CONFIG.scaleX), y);
            ctx.stroke();

            // 畫站名
            ctx.fillStyle = "#333333";
            ctx.fillText(st.name, 20, y);
        });

        // 🌟 這個區段畫完了，把這個區段的總長度加到累加器上，給下個區段（如南段）當起點
        currentAccumulatedKm += segMaxKm; 
    });

    // 動態調整 Canvas 總高度與寬度
    canvas.height = CONFIG.paddingTop + (currentAccumulatedKm * CONFIG.scaleY) + 100;
    canvas.width = CONFIG.paddingLeft + (1440 * CONFIG.scaleX) + 100;

    // 畫時間垂直線
    ctx.strokeStyle = "#dddddd";
    for (let h = 0; h <= 24; h++) {
        let x = timeToX(h * 60);
        ctx.beginPath();
        ctx.lineWidth = (h % 1 === 0) ? 1.5 : 0.5;
        ctx.moveTo(x, CONFIG.paddingTop);
        ctx.lineTo(x, canvas.height - CONFIG.paddingTop);
        ctx.stroke();
        ctx.fillStyle = "#999999";
        ctx.fillText(`${h}:00`, x - 15, CONFIG.paddingTop - 15);
    }
}

// ==========================================
// 繪製火車 (邏輯不變，完全依賴 lookupY 過濾)
// ==========================================
function drawTrains() {
    timetable.forEach(train => {
        ctx.strokeStyle = train.c || "#000000"; 
        ctx.lineWidth = train.w || 1.2;

        train.segments.forEach(seg => {
            ctx.beginPath();
            
            // 紀錄這條線有沒有成功下筆
            let isDrawing = false; 

            for (let i = 0; i < seg.s.length; i++) {
                let st_id = seg.s[i];
                let y = lookupY[st_id];
                
                // 🌟 如果切到山線視角，海線車站的 Y 會是 undefined，這裡直接跳過！
                if (y === undefined) {
                    isDrawing = false; // 斷開連線
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

                if (status !== 2) {
                    ctx.lineTo(x_dep, y);
                }
            }
            ctx.stroke();
        });
    });
}

// ==========================================
// 初始化與事件監聽
// ==========================================
async function init() {
    try {
        const topoRes = await fetch('topology.json');
        topology = await topoRes.json();
        const timeRes = await fetch('timetable.json');
        timetable = await timeRes.json();

        // 綁定選單切換事件
        routeSelect.addEventListener('change', (e) => {
            // 清空整張畫布
            ctx.clearRect(0, 0, canvas.width, canvas.height); 
            // 重新計算網格與 Y 座標
            drawGrid(e.target.value); 
            // 重新畫火車
            drawTrains(); 
        });

        // 初始載入時，觸發一次預設的山線繪製
        drawGrid(routeSelect.value);
        drawTrains();

    } catch (e) {
        console.error("載入失敗:", e);
    }
}

init();