module z8.runtime;

import z8.runtime_source : runtimeSource;

// Compile runtime declarations once in this separately linked library.
mixin(runtimeSource);
