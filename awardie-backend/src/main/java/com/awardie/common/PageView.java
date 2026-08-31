package com.awardie.common;

import java.util.List;

/** 轻量分页视图(#26):content/totalElements/totalPages/page(0 基)/size——JdbcTemplate 手写分页与 Spring Page 同构。 */
public record PageView<T>(List<T> content, long totalElements, int totalPages, int page, int size) {}
