// ============================================================
// Coco v6 — 屏幕组件 + 旋转平台 (独立 STL 导出)
// 200mm 圆屏，28° 仰角
// v6 新增: 屏幕组件可随头部水平旋转 (±50°)
// 用法: 打开此文件 → F6渲染 → Export as STL
// ============================================================
$fn = 120;

SCREEN_D   = 200;    // 屏直径
SCREEN_TILT = 28;    // 仰角
WALL       = 3;      // 壁厚

// 旋转平台参数
ROTATE_PLATFORM_D = 230;
ROTATE_PLATFORM_H = 5;
BEARING_RING_D = 80;
BEARING_RING_H = 4;
SHAFT_HOLE_D = 10;   // 舵机轴孔 + 走线孔

// 屏幕在旋转平台上的前伸量
SCREEN_OFFSET_FWD = 45;

// ===== 旋转平台底座 =====

module rotation_base() {
    difference() {
        union() {
            // 主平台
            color("#D0D4DC")
            cylinder(r=ROTATE_PLATFORM_D/2, h=ROTATE_PLATFORM_H);

            // 轴承配合环（向下伸入机身顶座凹槽）
            color("#50555A")
            translate([0, 0, -3])
            cylinder(r=BEARING_RING_D/2 + 2, h=3);

            // 屏幕支撑臂 — 从平台前缘向上延伸
            color("#D0D4DC")
            translate([0, 0, ROTATE_PLATFORM_H])
            rotate([0, -90, 0])
            rotate([SCREEN_TILT + 5, 0, 0])
            for(sy=[-SCREEN_D*0.4, SCREEN_D*0.4])
            translate([SCREEN_D*0.5 - 10, sy, 0])
            rotate([0, 0, 0])
            cylinder(r=14, h=SCREEN_OFFSET_FWD);
        }

        // 中心孔：舵机轴配合 + 走线通道
        translate([0, 0, -5])
        cylinder(r=SHAFT_HOLE_D, h=ROTATE_PLATFORM_H + 12);

        // 舵盘安装槽（底面）
        translate([0, 0, -0.5])
        cylinder(r=10, h=3);
    }
}


// ===== 屏幕主框架 =====

module screen_assembly() {
    sr = SCREEN_D / 2;

    // 固定在旋转平台上的相对位置
    translate([ROTATE_PLATFORM_D/2 - 5, 0, ROTATE_PLATFORM_H + 2])
    rotate([0, -90, 0])
    rotate([SCREEN_TILT, 0, 0]) {

        // === 1. 正面外框 ===
        color("#D0D4DC")
        difference() {
            cylinder(r=sr + 18, h=12);
            translate([0, 0, 2])
                cylinder(r=sr + 4, h=12);
            translate([0, 0, 10])
                cylinder(r=sr, h=8);
        }

        // === 2. 屏幕嵌入台阶 ===
        color("#B0B4BC")
        difference() {
            cylinder(r=sr + 4, h=10);
            translate([0, 0, 8])
                cylinder(r=sr - 2, h=5);
        }

        // === 3. 安装支耳 ×4 (M3 螺丝孔) ===
        for(a=[45, 135, 225, 315]) {
            rotate([0, 0, a])
            translate([sr + 14, 0, 2])
            color("#A0A4AC")
            difference() {
                hull() {
                    cylinder(r=8, h=6);
                    translate([-12, 0, 0]) cylinder(r=6, h=6);
                }
                translate([0, 0, -1])
                    cylinder(r=1.7, h=10);
            }
        }

        // === 4. 下方加厚支撑 ===
        color("#C0C4CC")
        translate([0, -sr - 10, 2])
        rotate([0, 0, 90])
        hull() {
            translate([-sr*0.6, 0, 0]) cylinder(r=6, h=6);
            translate([ sr*0.6, 0, 0]) cylinder(r=6, h=6);
        }

        // === 5. 麦克风安装槽 ===
        color("#C0C4CC")
        translate([0, -sr - 16, 0])
        rotate([0, 0, 90])
        difference() {
            hull() {
                translate([-38, 0, 0]) cylinder(r=6, h=6);
                translate([ 38, 0, 0]) cylinder(r=6, h=6);
            }
            translate([0, 0, 2])
            hull() {
                translate([-32, 0, 0]) cylinder(r=4, h=6);
                translate([ 32, 0, 0]) cylinder(r=4, h=6);
            }
            for(i=[0:3]) {
                translate([-22 + i*15, -1, 0])
                    cylinder(r=2, h=3);
            }
        }
    }
}


// ===== 尺寸标注 =====
echo("===== 屏幕组件 v6 (可转头) =====");
echo(str("适用屏幕: ", SCREEN_D, "mm 圆形HDMI屏"));
echo(str("仰角: ", SCREEN_TILT, "°"));
echo(str("安装孔: M3 ×4"));
echo(str("旋转平台: Ø", ROTATE_PLATFORM_D, "mm"));
echo(str("舵机轴孔: Ø", SHAFT_HOLE_D, "mm"));
echo(str("最大转角: ±50°"));
echo("用法: F6 → Export → STL");
echo("================================");

// 完整组件
rotation_base();
screen_assembly();
