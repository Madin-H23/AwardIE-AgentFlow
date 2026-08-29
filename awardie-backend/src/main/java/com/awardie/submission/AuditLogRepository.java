package com.awardie.submission;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

public interface AuditLogRepository extends JpaRepository<AuditLogEntity, Integer> {

    List<AuditLogEntity> findByAchievementIdOrderByCreatedAtAsc(Integer achievementId);
}
