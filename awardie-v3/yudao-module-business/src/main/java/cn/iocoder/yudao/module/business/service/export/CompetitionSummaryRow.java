package cn.iocoder.yudao.module.business.service.export;

/**
 * 竞赛 × 年份 × 获奖等级汇总行(批9)
 *
 * @author AwardIE
 */
public class CompetitionSummaryRow {

    private String competition;
    private Integer year;
    private String awardLevel;
    private Long count;

    public String getCompetition() {
        return competition;
    }

    public void setCompetition(String competition) {
        this.competition = competition;
    }

    public Integer getYear() {
        return year;
    }

    public void setYear(Integer year) {
        this.year = year;
    }

    public String getAwardLevel() {
        return awardLevel;
    }

    public void setAwardLevel(String awardLevel) {
        this.awardLevel = awardLevel;
    }

    public Long getCount() {
        return count;
    }

    public void setCount(Long count) {
        this.count = count;
    }

}
