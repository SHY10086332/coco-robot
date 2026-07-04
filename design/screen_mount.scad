// ============================================================
// Coco v6.2 — 双轴云台完整头部组件 (刚性一体, STL导出)
// 屏幕+外壳+天线 整个头部绕铰链俯仰
// 与 coco_model.scad 坐标完全一致
// SG90 ×2: pan ±50° + tilt 5°~55°
// ============================================================
$fn = 120;

SCREEN_D     = 200;
SCREEN_TILT  = 28;

ROTATE_PLATFORM_D = 220;
ROTATE_PLATFORM_H = 5;
BEARING_RING_D = 80;
SHAFT_HOLE_D = 10;

TILT_ANGLE = 28;
TILT_MIN = 5;
TILT_MAX = 55;

// SG90 舵机尺寸
SERVO_W = 12.5; SERVO_L = 23.0; SERVO_H = 29.0;

// 颜色
C_WHITE    = "#F7F8FA";
C_BLUE     = "#4A90D9";
C_BLUE_DK  = "#2C5F8A";
C_CYAN     = "#00FFD0";
C_SCREEN   = "#0A0C12";
C_GRAY     = "#3A3C42";
C_SILVER   = "#D0D4DC";
C_GOLD     = "#FFD700";
C_SERVO_PAN  = "#4488CC";
C_SERVO_TILT = "#CC6644";

module ring(r, h, t) {
    difference() { cylinder(r=r,h=h,center=true); cylinder(r=r-t,h=h+2,center=true); }
}

// ===== 旋转底盘 =====
module rotation_base() {
    difference() {
        union() {
            color("#D0D4DC") cylinder(r=ROTATE_PLATFORM_D/2, h=ROTATE_PLATFORM_H);
            color("#50555A") translate([0,0,-3]) cylinder(r=BEARING_RING_D/2+2, h=3);
        }
        translate([0,0,-5]) cylinder(r=SHAFT_HOLE_D, h=ROTATE_PLATFORM_H+12);
    }
}

// ===== Pan舵机安装座 =====
module pan_servo_mount() {
    color(C_SERVO_PAN)
    translate([BEARING_RING_D/2-5, -SERVO_W/2, ROTATE_PLATFORM_H-24])
    difference() {
        union() {
            cube([SERVO_L, SERVO_W, SERVO_H-6]);
            translate([0, 0, SERVO_H-6]) cube([SERVO_L, SERVO_W+16, 1.5]);
        }
        for(dx=[-SERVO_L*0.35, SERVO_L*0.35])
            translate([SERVO_L/2+dx, SERVO_W/2, SERVO_H+2])
            cylinder(r=1.5, h=10);
    }
    color("#CCCCCC")
    translate([BEARING_RING_D/2-5+SERVO_L/2, 0, ROTATE_PLATFORM_H-24+SERVO_H])
    cylinder(r=SERVO_W/4, h=ROTATE_PLATFORM_H+3);
    color("#DDDDDD")
    translate([BEARING_RING_D/2-5+SERVO_L/2, 0, ROTATE_PLATFORM_H+0.5])
    cylinder(r=9, h=3);
}

// ===== 铰链支架 (在旋转平台上) =====
module tilt_hinge_brackets() {
    pivot_x = 48;
    pivot_z_offset = 24;
    color("#B0B4BC")
    for(sy=[-BEARING_RING_D/2-4, BEARING_RING_D/2+4])
    translate([pivot_x, sy, ROTATE_PLATFORM_H])
    difference() {
        hull() {
            cylinder(r=7, h=pivot_z_offset);
            translate([-12, 0, 0]) cylinder(r=5, h=pivot_z_offset);
        }
        translate([0, 0, pivot_z_offset])
        rotate([0, 90, 0])
        cylinder(r=3.2, h=30, center=true);
    }
}

// ===== Tilt舵机座 =====
module tilt_servo_mount() {
    tilt_servo_x = 78;
    tilt_servo_z = 6;
    color(C_SERVO_TILT)
    translate([tilt_servo_x, -SERVO_W/2, ROTATE_PLATFORM_H + tilt_servo_z]) {
        cube([SERVO_L, SERVO_W, SERVO_H-4]);
        translate([0, -SERVO_W/2, SERVO_H-4]) cube([SERVO_L, SERVO_W+16, 1.5]);
        translate([SERVO_L/2, SERVO_W/2, SERVO_H])
        cylinder(r=SERVO_W/4, h=5);
        translate([SERVO_L/2, SERVO_W/2, SERVO_H+5]) cylinder(r=8, h=2);
    }
}

// ===== Tilt 连杆 =====
module tilt_linkage() {
    tilt_servo_x = 78;
    tilt_servo_z = 6;
    pivot_x = 48;
    color("#888C94")
    translate([tilt_servo_x + SERVO_L/2, SERVO_W/2, ROTATE_PLATFORM_H + tilt_servo_z + SERVO_H + 7])
    hull() {
        cylinder(r=3, h=2);
        translate([pivot_x - tilt_servo_x - SERVO_L/2, 0, 38]) cylinder(r=3, h=2);
    }
}

// ===== 完整头部 (刚性一体, 与coco_model.scad一致) =====
module head_assembly() {
    sr = SCREEN_D / 2;
    screen_dx = 58;
    screen_dz = 42;
    shell_cx = -5;
    shell_cz = 52;
    shell_r  = sr + 45;
    ant_dx = -15;
    ant_dz = 128;

    // -- 屏幕外框 --
    translate([screen_dx, 0, screen_dz])
    rotate([SCREEN_TILT, 0, 0]) {
        color(C_SILVER)
        difference() {
            cylinder(r=sr+18, h=12);
            translate([0,0,2]) cylinder(r=sr+6, h=12);
        }
        color("#B0B4BC")
        translate([0,0,12])
        difference() {
            cylinder(r=sr+6, h=4);
            translate([0,0,-1]) cylinder(r=sr-2, h=7);
        }
        for(a=[45,135,225,315])
        rotate([0,0,a])
        translate([sr+13, 0, 0])
        color("#A0A4AC")
        difference() {
            hull() { cylinder(r=8,h=6); translate([-12,0,0]) cylinder(r=5,h=6); }
            translate([0,0,-1]) cylinder(r=1.7,h=10);
        }
        color(C_SCREEN) translate([0,0,15]) cylinder(r=sr-1, h=1.5);
        // 表情
        translate([0, 0, 16.5]) {
            for(ex=[-1,1]) {
                color(C_CYAN) translate([ex*sr*0.32, sr*0.08, 0])
                scale([1,1.25,1]) cylinder(r=sr*0.24, h=1.2);
                color("#0A0C12") translate([ex*sr*0.32, sr*0.06, 1.2])
                cylinder(r=sr*0.24*0.35, h=1);
                color("#FFFFFF") translate([ex*sr*0.35, sr*0.03, 2.2])
                cylinder(r=sr*0.24*0.1, h=0.5);
            }
            color(C_CYAN) translate([0,-sr*0.12,0])
            difference() {
                cylinder(r=sr*0.28, h=1.2);
                translate([0,sr*0.22,-1]) cylinder(r=sr*0.31, h=3);
            }
            for(ex=[-1,1])
            color("#FF9999") translate([ex*sr*0.54, -sr*0.16, 0])
            scale([1,0.6,1]) cylinder(r=sr*0.09, h=1.2);
        }
    }

    // -- 头部后壳 --
    translate([shell_cx, 0, shell_cz])
    rotate([SCREEN_TILT, 0, 0])
    difference() {
        scale([1, 0.82, 0.92])
        rotate([-3, 0, 0])
        sphere(r=shell_r);
        translate([shell_r-10, -shell_r-20, -shell_r])
        cube([shell_r+10, (shell_r+20)*2, (shell_r+30)*2]);
        translate([-shell_r-10, -shell_r-20, -shell_r-10])
        cube([(shell_r+10)*2, (shell_r+20)*2, shell_cz - screen_dz + sr + 10]);
    }
    translate([shell_cx, 0, shell_cz+sr*0.4])
    rotate([SCREEN_TILT, 0, 0])
    scale([1, 0.82, 0.92]) rotate([-3,0,0])
    ring(r=shell_r+2, h=5, t=3);

    // -- 天线 --
    translate([ant_dx, -4, ant_dz])
    rotate([SCREEN_TILT-3, 0, 0]) {
        color(C_BLUE_DK) {
            cylinder(h=10, r1=13, r2=7);
            translate([0,0,10]) cylinder(h=4, r1=7, r2=3.5);
        }
        color(C_BLUE_DK) translate([0,0,14]) cylinder(h=55, r1=3.5, r2=2);
        translate([0,0,69]) color(C_GOLD) sphere(r=15);
        translate([-5,5,76]) color("#FFF5A0") sphere(r=4);
    }

    // -- 铰链耳 --
    for(sy=[-BEARING_RING_D/2-4, BEARING_RING_D/2+4])
    translate([0, sy, 0])
    rotate([0, 90, 0])
    color("#B0B4BC")
    difference() {
        cylinder(r=7, h=14);
        cylinder(r=3.3, h=20, center=true);
    }

    // -- 连杆球头 --
    translate([42, 0, -8])
    color("#888C94")
    sphere(r=4.5);
}


// ===== 主装配 =====
pivot_x = 48;
pivot_y = 0;
pivot_z_local = ROTATE_PLATFORM_H + 24;

echo("===== Coco v6.2 头部组件 =====");
echo(str("屏幕: Ø", SCREEN_D, "mm"));
echo(str("仰角: ", TILT_MIN, "°~", TILT_MAX, "° (当前=", TILT_ANGLE, "°)"));
echo(str("铰链轴: x=", pivot_x, " z=", pivot_z_local));
echo("屏幕+外壳+天线 刚性一体俯仰");
echo("==============================");

// 固定部分
rotation_base();
pan_servo_mount();
tilt_hinge_brackets();
tilt_servo_mount();
tilt_linkage();

// 头部绕铰链俯仰
translate([pivot_x, pivot_y, pivot_z_local])
rotate([-TILT_ANGLE + SCREEN_TILT, 0, 0])
translate([-pivot_x, -pivot_y, -pivot_z_local])
head_assembly();
