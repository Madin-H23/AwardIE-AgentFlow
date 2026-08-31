package com.awardie.submission;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface PendingAchievementRepository
		extends JpaRepository<PendingAchievementEntity, Integer>, JpaSpecificationExecutor<PendingAchievementEntity> {

    List<PendingAchievementEntity> findBySubmitterIdOrderByCreatedAtDesc(Integer submitterId);

    Optional<PendingAchievementEntity> findByFileHashAndStatus(String fileHash, String status);

    Optional<PendingAchievementEntity> findByFileHash(String fileHash);
}
