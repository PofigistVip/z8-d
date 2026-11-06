module z8.database.bootstrap;

import z8.runtime;
import z8.database.metadata : z8_postgres_sync_registry;
import z8.database.migration : z8_postgres_reconcile_schema;
import z8.database.plan : quoteIdentifier;
import z8.database.postgres : Z8PostgresConnection, Z8PostgresException;
import z8.database.schema;

// Build fresh registered table instances and optionally include framework
// tables supplied by the host, then run the normal atomic bootstrap.
void z8_postgres_bootstrap_registered(Z8PostgresConnection db, wstring schema, Z8RuntimeRegistry registry, Z8Object[] additionalTables = null) {
    if (registry is null) throw new Z8PostgresException("application registry is required");
    z8_postgres_bootstrap(db, schema, additionalTables ~ registry.newTables(), registry);
}

// Reconcile registered and platform tables and update the registry atomically.
// Existing table data and existing permission settings are preserved.
string[] z8_postgres_reconcile_registered(Z8PostgresConnection db, wstring schema, Z8RuntimeRegistry registry, Z8Object[] additionalTables = null) {
    if (registry is null) throw new Z8PostgresException("application registry is required");
    auto request = z8_application_request();
    auto temporaryRequest = request is null;
    if (temporaryRequest) {
        request = new Z8ApplicationRequest(); request.setEventsLevel(Z8EventsLevel.none);
        z8_application_set_request(request);
    } else request.setEventsLevel(Z8EventsLevel.system);
    scope(exit) {
        if (temporaryRequest) z8_application_set_request(null);
        else request.restoreEventsLevel();
    }
    return z8_postgres_reconcile_schema(db, schema, additionalTables ~ registry.newTables(), registry);
}

// Bootstrap new tables, built-in records and the additive access metadata in a
// single transaction. The caller supplies the schema, table instances, and the
// complete registry; no existing table is recreated or dropped.
void z8_postgres_bootstrap(Z8PostgresConnection db, wstring schema, Z8Object[] tables, Z8RuntimeRegistry registry) {
    if (db is null || db.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
    if (registry is null) throw new Z8PostgresException("application registry is required");
    if (db.inTransaction()) throw new Z8PostgresException("schema bootstrap requires its own transaction");
    quoteIdentifier(schema);
    auto request = z8_application_request();
    auto temporaryRequest = request is null;
    if (temporaryRequest) {
        request = new Z8ApplicationRequest(); request.setEventsLevel(Z8EventsLevel.none);
        z8_application_set_request(request);
    } else {
        request.setEventsLevel(Z8EventsLevel.system);
    }
    scope(exit) {
        if (temporaryRequest) z8_application_set_request(null);
        else request.restoreEventsLevel();
    }
    string[] definitions, indexes, foreignKeys;
    wstring[] names;
    foreach (table; tables) {
        definitions ~= z8_postgres_create_table_sql(schema, table);
        auto name = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, table);
        foreach (existing; names) if (existing == name) throw new Z8PostgresException("duplicate PostgreSQL table name");
        names ~= name;
        indexes ~= z8_postgres_create_indexes_sql(schema, table);
        foreignKeys ~= z8_postgres_create_foreign_keys_sql(schema, table);
    }
    db.beginTransaction();
    try {
        z8_postgres_lock_schema(db, schema);
        foreach (sql; definitions) db.execute(sql);
        foreach (table; tables) z8_postgres_ensure_null_record(db, schema, table);
        foreach (table; tables) z8_postgres_apply_static_records(db, schema, table, registry);
        z8_postgres_sync_registry(db, schema, registry);
        foreach (sql; indexes) db.execute(sql);
        foreach (sql; foreignKeys) db.execute(sql);
        db.commit();
    } catch (Throwable failure) {
        try { db.rollback(); } catch (Throwable ignored) { }
        throw failure;
    }
}
