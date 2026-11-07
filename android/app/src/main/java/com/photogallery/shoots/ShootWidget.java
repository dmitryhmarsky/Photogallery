package com.photogallery.shoots;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

/** Базовый класс виджетов. Данные приходят из приложения (SharedPreferences "events"). */
public abstract class ShootWidget extends AppWidgetProvider {
    static final String PREFS = "shoots_widget";

    abstract int layout();
    abstract int[] whenIds();
    abstract int[] titleIds();
    abstract int[] subIds();
    abstract int[] rowIds();

    @Override
    public void onUpdate(Context ctx, AppWidgetManager mgr, int[] ids) {
        for (int id : ids) mgr.updateAppWidget(id, build(ctx));
    }

    RemoteViews build(Context ctx) {
        RemoteViews rv = new RemoteViews(ctx.getPackageName(), layout());
        JSONArray arr;
        try {
            arr = new JSONArray(ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("events", "[]"));
        } catch (Exception e) { arr = new JSONArray(); }
        long now = System.currentTimeMillis();
        int n = whenIds().length, shown = 0;
        for (int i = 0; i < arr.length() && shown < n; i++) {
            JSONObject o = arr.optJSONObject(i);
            if (o == null) continue;
            if (o.optLong("ts", 0) + 2 * 3600_000L < now) continue; // уже прошла
            rv.setViewVisibility(rowIds()[shown], android.view.View.VISIBLE);
            rv.setTextViewText(whenIds()[shown], o.optString("when"));
            rv.setTextViewText(titleIds()[shown], o.optString("title"));
            String sub = o.optString("sub");
            rv.setTextViewText(subIds()[shown], sub);
            rv.setViewVisibility(subIds()[shown], sub.isEmpty() ? android.view.View.GONE : android.view.View.VISIBLE);
            shown++;
        }
        for (int k = shown; k < n; k++) rv.setViewVisibility(rowIds()[k], android.view.View.GONE);
        rv.setViewVisibility(R.id.empty, shown == 0 ? android.view.View.VISIBLE : android.view.View.GONE);
        Intent open = new Intent(ctx, MainActivity.class).setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(ctx, 0, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        rv.setOnClickPendingIntent(R.id.root, pi);
        return rv;
    }

    static void refreshAll(Context ctx) {
        AppWidgetManager mgr = AppWidgetManager.getInstance(ctx);
        Class<?>[] kinds = {SmallWidget.class, MediumWidget.class, LargeWidget.class};
        for (Class<?> k : kinds) {
            ComponentName cn = new ComponentName(ctx, k);
            int[] ids = mgr.getAppWidgetIds(cn);
            if (ids.length == 0) continue;
            Intent i = new Intent(ctx, k).setAction(AppWidgetManager.ACTION_APPWIDGET_UPDATE)
                    .putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids);
            ctx.sendBroadcast(i);
        }
    }
}
