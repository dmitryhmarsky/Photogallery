package com.photogallery.shoots;

import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.content.Context;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "WidgetBridge")
public class WidgetBridgePlugin extends Plugin {
    @PluginMethod
    public void update(PluginCall call) {
        String json = call.getString("json", "[]");
        Context c = getContext();
        c.getSharedPreferences(ShootWidget.PREFS, Context.MODE_PRIVATE).edit().putString("events", json).apply();
        ShootWidget.refreshAll(c);
        JSObject r = new JSObject();
        r.put("ok", true);
        call.resolve(r);
    }
}
