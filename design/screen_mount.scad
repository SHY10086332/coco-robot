// ============================================================
// Coco v6.2 — 双轴云台头部组件 (pan + tilt, 独立导出)
// 200mm圆屏, 5°~55°仰角自适应, 站立平视高度 (~840mm)
// SG90 ×2: pan ±50°水平旋转 + tilt 5°~55°俯仰
// 用法: 打开此文件 → F6渲染 → Export as STL
// ============================================================
$fn = 120;

SCREEN_D     = 200;
SCREEN_TILT  = 28;
SCREEN_LIFT  = 60;

ROTATE_PLATFORM_D = 230;
ROTATE_PLATFORM_H = 5;
BEARING_RING_D = 80;
SHAFT_HOLE_D = 10;

// 俯仰参数
TILT_ANGLE = 28;   // 当前仰角 (5~55), 可调预览
TILT_MIN = 5;
TILT_MAX = 55;

// ===== 旋转底盘 (pan轴) =====
module rotation_base() {
    difference() {
        union() {
            color("#D0D4DC") cylinder(r=ROTATE_PLATFORM_D/2, h=ROTATE_PLATFORM_H);
            color("#50555A") translate([0,0,-3]) cylinder(r=BEARING_RING_D/2+2, h=3);
        }
        translate([0,0,-5]) cylinder(r=SHAFT_HOLE_D, h=ROTATE_PLATFORM_H+12);
        translate([0,0,-0.5]) cylinder(r=10, h=3);  // 舵盘槽
    }
}

// ===== Pan舵机安装座 =====
module pan_servo_mount() {
    color("#C8CCD4")
    translate([BEARING_RING_D/2-5, -15, ROTATE_PLATFORM_H])
    difference() {
        union() {
            cube([18, 30, 6]);
            translate([0, 0, -ROTATE_PLATFORM_H])
            cube([12, 30, ROTATE_PLATFORM_H]);
        }
        // M2螺丝孔
        translate([9, 5, -10]) cylinder(r=1.2, h=20);
        translate([9, 25, -10]) cylinder(r=1.2, h=20);
    }
}

// ===== 俯仰铰链支架 (在旋转平台上) =====
module tilt_hinge_brackets() {
    sr = SCREEN_D/2;
    color("#B8BCC4")
    translate([ROTATE_PLATFORM_D/2-25, 0, ROTATE_PLATFORM_H])
    for(sx=[-sr*0.25, sr*0.25])
    translate([sx, 0, 0])
    difference() {
        hull() {
            translate([0, -12, 0]) cylinder(r=8, h=25);
            translate([0, 12, 0]) cylinder(r=8, h=25);
        }
        // 铰链轴孔 Ø4mm
        translate([0, 0, 18]) rotate([0,90,0]) cylinder(r=2.1, h=30, center=true);
    }
}

// ===== 俯仰舵机安装座 (在旋转平台上, 屏幕后方) =====
module tilt_servo_mount() {
    sr = SCREEN_D/2;
    color("#CC6644")
    translate([ROTATE_PLATFORM_D/2-25, -sr*0.5, ROTATE_PLATFORM_H+5])
    difference() {
        union() {
            cube([24, 16, 20], center=true);
            translate([0, 0, -ROTATE_PLATFORM_H-5])
            cube([16, 16, ROTATE_PLATFORM_H+5], center=true);
        }
        // 舵机安装孔
        translate([0, 0, 6]) rotate([0,90,0]) cylinder(r=4, h=30, center=true);
        translate([0, 0, -8]) rotate([0,90,0]) cylinder(r=1.5, h=30, center=true);
    }
}

// ===== 屏幕框架 (带铰链耳) =====
module screen_frame_with_hinge() {
    sr = SCREEN_D/2;
    lift = SCREEN_LIFT;

    translate([ROTATE_PLATFORM_D/2-10, 0, ROTATE_PLATFORM_H + lift])
    rotate([SCREEN_TILT, 0, 0]) {

        // 外框
        color("#D0D4DC")
        difference() {
            cylinder(r=sr+18, h=12);
            translate([0,0,2]) cylinder(r=sr+4, h=12);
            translate([0,0,10]) cylinder(r=sr, h=8);
        }

        // 屏幕嵌入台阶
        color("#B0B4BC")
        difference() {
            cylinder(r=sr+4, h=10);
            translate([0,0,8]) cylinder(r=sr-2, h=5);
        }

        // 安装支耳 ×4 (M3)
        for(a=[45,135,225,315])
        rotate([0,0,a]) translate([sr+14,0,2])
        color("#A0A4AC")
        difference() {
            hull() { cylinder(r=8,h=6); translate([-12,0,0]) cylinder(r=6,h=6); }
            translate([0,0,-1]) cylinder(r=1.7,h=10);
        }

        // 下方加强筋
        color("#C0C4CC")
        translate([0,-sr-10,2]) rotate([0,0,90])
        hull() { translate([-sr*0.6,0,0]) cylinder(r=6,h=6); translate([sr*0.6,0,0]) cylinder(r=6,h=6); }
    }

    // 铰链耳 (连接屏幕框到铰链支架)
    sr = SCREEN_D/2;
    color("#B8BCC4")
    translate([ROTATE_PLATFORM_D/2-25, 0, ROTATE_PLATFORM_H + SCREEN_LIFT])
    for(sx=[-sr*0.25, sr*0.25])
    translate([sx, 0, 20])
    rotate([SCREEN_TILT, 0, 0])
    difference() {
        cylinder(r=7, h=6);
        rotate([0,90,0]) cylinder(r=2.1, h=20, center=true);
    }
}

// ===== 俯仰连杆 (从tilt舵机到屏幕框) =====
module tilt_linkage() {
    sr = SCREEN_D/2;
    color("#888C94")
    translate([ROTATE_PLATFORM_D/2-25, -sr*0.5, ROTATE_PLATFORM_H+15])
    rotate([-TILT_ANGLE+SCREEN_TILT, 0, 0])
    translate([0, 0, -10])
    hull() {
        cylinder(r=3, h=30);
        translate([0, 15, 0]) cylinder(r=3, h=30);
    }
}

// ===== 屏幕支撑柱 (简化, 含铰链功能) =====
module screen_supports() {
    sr = SCREEN_D/2;
    color("#C8CBD2")
    translate([ROTATE_PLATFORM_D/2-25, 0, ROTATE_PLATFORM_H])
    rotate([0, -90, 0])
    for(sy=[-sr*0.3, sr*0.3])
    translate([SCREEN_LIFT*0.3, sy, 0])
    hull() {
        translate([0,0,0]) cylinder(r=14,h=20);
        translate([SCREEN_LIFT*0.7,0,0]) cylinder(r=8,h=20);
    }
}


// ===== 主装配 =====
echo("===== 双轴云台头部组件 v6.2 =====");
echo(str("屏幕: ", SCREEN_D, "mm, 仰角范围 ", TILT_MIN, "°~", TILT_MAX, "°"));
echo(str("屏幕中心高: ~", 60+700+ROTATE_PLATFORM_H+SCREEN_LIFT, "mm"));
echo(str("旋转平台: Ø", ROTATE_PLATFORM_D, "mm"));
echo(str("舵机: SG90 ×2 (pan + tilt)"));
echo(str("pan: ±50°水平, tilt: 5°~55°俯仰"));
echo("用法: F6 → Export → STL");
echo("==============================");

rotation_base();
pan_servo_mount();
screen_supports();
tilt_hinge_brackets();
tilt_servo_mount();
screen_frame_with_hinge();
tilt_linkage();
