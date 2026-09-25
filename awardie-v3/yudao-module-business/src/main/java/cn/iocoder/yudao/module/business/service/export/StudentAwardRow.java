package cn.iocoder.yudao.module.business.service.export;

/**
 * 学生获奖明细行(批9)
 *
 * <p><b>studentNo 取 system_users.username</b>——v3 的 username 就是学号(批2 ETL 把 v2
 * {@code login_code} 映射过来,实测 1792 个纯数字账号)。v2 导出选的是
 * {@code award_student_winners.student_id}(那是 users.id 内部主键),表头写着"学号"
 * 内容却是数字 ID,学工拿到还得二次加工——本批修掉。
 *
 * @author AwardIE
 */
public class StudentAwardRow {

    private String studentNo;
    private String studentName;
    private String competition;
    private String awardLevel;
    private Integer year;

    public String getStudentNo() {
        return studentNo;
    }

    public void setStudentNo(String studentNo) {
        this.studentNo = studentNo;
    }

    public String getStudentName() {
        return studentName;
    }

    public void setStudentName(String studentName) {
        this.studentName = studentName;
    }

    public String getCompetition() {
        return competition;
    }

    public void setCompetition(String competition) {
        this.competition = competition;
    }

    public String getAwardLevel() {
        return awardLevel;
    }

    public void setAwardLevel(String awardLevel) {
        this.awardLevel = awardLevel;
    }

    public Integer getYear() {
        return year;
    }

    public void setYear(Integer year) {
        this.year = year;
    }

}
