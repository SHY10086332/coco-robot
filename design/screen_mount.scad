// ============================================================
// Coco v5 — 屏幕组件 (独立 STL 导出)
// 200mm 圆屏，28° 仰角，含安装支架和螺丝孔
// 用法: 打开此文件 → F6渲染 → Export as STL
// ============================================================
$fn = 120;

SCREEN_D   = 200;    // 屏直径
SCREEN_TILT = 28;    // 仰角
WALL       = 3;      // 壁厚

// ===== 主框架 =====

module screen_assembly() {
    sr = SCREEN_D / 2;

    rotate([SCREEN_TILT, 0, 0]) {

        // === 1. 正面外框 (露出机身的部分) ===
        color("#D0D4DC")
        difference() {
            // 外框主体
            cylinder(r=sr + 18, h=12);
            // 屏幕安装槽
            translate([0, 0, 2])
                cylinder(r=sr + 4, h=12);
            // 屏幕显示面镂空
            translate([0, 0, 10])
                cylinder(r=sr, h=8);
        }

        // === 2. 屏幕嵌入台阶 ===
        color("#B0B4BC")
        difference() {
            cylinder(r=sr + 4, h=10);
            // 实际屏幕位
            translate([0, 0, 8])
                cylinder(r=sr - 2, h=5);
        }

        // === 3. 安装支耳 ×4 (带螺丝孔) ===
        for(a=[45, 135, 225, 315]) {
            rotate([0, 0, a])
            translate([sr + 14, 0, 2])
            color("#A0A4AC")
            difference() {
                hull() {
                    cylinder(r=8, h=6);
                    translate([-12, 0, 0]) cylinder(r=6, h=6);
                }
                // M3 螺丝孔
                translate([0, 0, -1])
                    cylinder(r=1.7, h=10);
            }
        }

        // === 4. 上方遮光罩 (屏倾角导致顶部不需要) ===
        // 下方加厚支撑 (屏幕底部承重)
        color("#C0C4CC")
        translate([0, -sr - 10, 2])
        rotate([0, 0, 90])
        hull() {
            translate([-sr*0.6, 0, 0]) cylinder(r=6, h=6);
            translate([ sr*0.6, 0, 0]) cylinder(r=6, h=6);
        }

        // === 5. 麦克风安装槽 (屏幕正下方) ===
        color("#C0C4CC")
        translate([0, -sr - 16, 0])
        rotate([0, 0, 90])
        difference() {
            hull() {
                translate([-38, 0, 0]) cylinder(r=6, h=6);
                translate([ 38, 0, 0]) cylinder(r=6, h=6);
            }
            // 麦克风腔体
            translate([0, 0, 2])
            hull() {
                translate([-32, 0, 0]) cylinder(r=4, h=6);
                translate([ 32, 0, 0]) cylinder(r=4, h=6);
            }
            // 拾音孔 ×4
            for(i=[0:3]) {
                translate([-22 + i*15, -1, 0])
                    cylinder(r=2, h=3);
            }
        }
    }
}

// ===== 尺寸标注 =====
echo("===== 屏幕组件 =====");
echo(str("适用屏幕: ", SCREEN_D, "mm 圆形HDMI屏"));
echo(str("仰角: ", SCREEN_TILT, "°"));
echo(str("安装孔: M3 ×4, 间距 ~", (SCREEN_D/2 + 14)*2, "mm"));
echo(str("外框直径: ~", SCREEN_D + 36, "mm"));
echo("用法: F6 → Export → STL");
echo("====================");

screen_assembly();
