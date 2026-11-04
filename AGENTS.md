# Project development

When splitting or reorganizing compiler or runtime code, inspect the corresponding
original Z8 sources first and use their responsibilities and module boundaries to
inform the D design. The reference checkout for this workspace is
`C:/Users/volod/eclipse/jee-2022-12/z8-homer-workspace/org.zenframework.z8`.
Adapt the structure to D and to the implemented scope; do not copy Java classes
mechanically. If the reference checkout is unavailable, say so when reporting the
work rather than claiming that the original was consulted.
