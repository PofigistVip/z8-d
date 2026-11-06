module z8.database.scheduler_service;

import core.sync.condition : Condition;
import core.sync.mutex : Mutex;
import core.thread : Thread;
import core.time : dur;
import std.conv : to;
import z8.runtime : Z8RuntimeRegistry, IZ8UserChangeNotifier, IZ8RoleChangeNotifier;
import z8.database.postgres : Z8PostgresConnection, Z8PostgresException;
import z8.database.scheduler : Z8PostgresScheduler, Z8ScheduledRun;
import z8.database.scheduler_logs : IZ8SchedulerLogStore;

// Observer methods run on the scheduler thread and must be thread-safe.
interface IZ8SchedulerObserver {
    void onRuns(Z8ScheduledRun[] runs);
    void onError(wstring message);
}

class Z8PostgresSchedulerService {
    private Z8PostgresConnection source;
    private wstring schema;
    private Z8RuntimeRegistry registry;
    private IZ8SchedulerObserver observer;
    private IZ8UserChangeNotifier userNotifier;
    private IZ8RoleChangeNotifier roleNotifier;
    private IZ8SchedulerLogStore logStore;
    private long intervalMilliseconds;
    private Mutex gate;
    private Condition wake;
    private Thread worker;
    private bool stopping, alive;
    private wstring lastFailure;

    this(Z8PostgresConnection source, wstring schema, Z8RuntimeRegistry registry,
         long intervalMilliseconds = 1000, IZ8SchedulerObserver observer = null,
         IZ8UserChangeNotifier userNotifier = null, IZ8RoleChangeNotifier roleNotifier = null, IZ8SchedulerLogStore logStore = null) {
        if (source is null || source.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
        if (schema is null || !schema.length || registry is null) throw new Z8PostgresException("scheduler schema and registry are required");
        if (intervalMilliseconds <= 0) throw new Z8PostgresException("scheduler interval must be positive");
        this.source = source; this.schema = schema.idup; this.registry = registry;
        this.intervalMilliseconds = intervalMilliseconds; this.observer = observer;
        this.userNotifier = userNotifier; this.roleNotifier = roleNotifier;
        this.logStore = logStore;
        gate = new Mutex(); wake = new Condition(gate);
    }
    bool isRunning() { synchronized (gate) return worker !is null && alive && !stopping; }
    wstring lastError() { synchronized (gate) return lastFailure; }
    // Idempotent. A sibling connection belongs to the worker and is closed on stop.
    void start() {
        synchronized (gate) {
            if (worker !is null) return;
            auto connection = source.openSibling();
            scope(failure) connection.close();
            stopping = false; alive = true; lastFailure = null;
            auto thread = new Thread({ run(connection); });
            worker = thread;
            try { thread.start(); }
            catch (Throwable failure) { worker = null; alive = false; throw failure; }
        }
    }
    // Wait for the active synchronous job to finish; do not interrupt BL code.
    void stop() {
        Thread thread;
        synchronized (gate) {
            if (worker is null) return;
            if (Thread.getThis() is worker) throw new Z8PostgresException("scheduler cannot join its own thread");
            if (stopping) {
                while (worker !is null) wake.wait();
                return;
            }
            stopping = true; thread = worker; wake.notifyAll();
        }
        scope(exit) synchronized (gate) { worker = null; stopping = false; wake.notifyAll(); }
        thread.join();
    }
    private void report(Throwable failure) {
        auto message = failure.msg.to!wstring;
        synchronized (gate) lastFailure = message;
        if (observer !is null) { try { observer.onError(message); } catch (Throwable ignored) { } }
    }
    private void run(Z8PostgresConnection connection) {
        scope(exit) synchronized (gate) { alive = false; wake.notifyAll(); }
        try {
            auto scheduler = new Z8PostgresScheduler(connection, schema, registry, userNotifier, roleNotifier, logStore);
            for (;;) {
                synchronized (gate) if (stopping) break;
                try {
                    auto runs = scheduler.runDue();
                    if (runs.length && observer !is null) observer.onRuns(runs);
                } catch (Throwable failure) { report(failure); }
                synchronized (gate) {
                    if (stopping) break;
                    wake.wait(dur!"msecs"(intervalMilliseconds));
                }
            }
        } catch (Throwable failure) { report(failure); }
        try { connection.close(); } catch (Throwable failure) { report(failure); }
    }
}
