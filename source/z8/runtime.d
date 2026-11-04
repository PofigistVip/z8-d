module z8.runtime;

import z8.runtime_source : runtimeSource;

// Compile the exact runtime emitted into standalone programs during each build.
mixin(runtimeSource);
