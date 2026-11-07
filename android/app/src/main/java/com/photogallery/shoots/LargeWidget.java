package com.photogallery.shoots;

public class LargeWidget extends ShootWidget {
    int layout() { return R.layout.widget_large; }
    int[] whenIds() { return new int[]{R.id.w1, R.id.w2, R.id.w3, R.id.w4, R.id.w5, R.id.w6}; }
    int[] titleIds() { return new int[]{R.id.t1, R.id.t2, R.id.t3, R.id.t4, R.id.t5, R.id.t6}; }
    int[] subIds() { return new int[]{R.id.s1, R.id.s2, R.id.s3, R.id.s4, R.id.s5, R.id.s6}; }
    int[] rowIds() { return new int[]{R.id.r1, R.id.r2, R.id.r3, R.id.r4, R.id.r5, R.id.r6}; }
}
