package com.awardie.submission;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface PendingAchievementRepository extends JpaRepository<PendingAchievementEntity, Integer> {

    List<PendingAchievementEntity> findBySubmitterIdOrderByCreatedAtDesc(Integer submitterId);

    Optional<PendingAchievementEntity> findByFileHashAndStatus(String fileHash, String status);

    Optional<PendingAchievementEntity> findByFileHash(String fileHash);
}
