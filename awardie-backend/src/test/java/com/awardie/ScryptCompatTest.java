package com.awardie;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.jupiter.api.Test;

import com.awardie.auth.security.WerkzeugCompatPasswordEncoder;

class ScryptCompatTest {

    @Test
    void probeAdminBcrypt() throws Exception {
        String hash = Files.readString(Path.of("D:/Develop/AI 应用开发/AI应用开发项目/AwardIE-AgentFlow/tmp_admin_hash.txt")).trim();
        WerkzeugCompatPasswordEncoder enc = new WerkzeugCompatPasswordEncoder();
        System.out.println("[probe] hash=" + hash.substring(0, 12));
        for (String pwd : new String[]{"Mayy123", "short1", "NewPass123", "P@ss301", "nope"}) {
            System.out.println("[probe] " + pwd + " -> " + enc.matches(pwd, hash));
        }
    }
}
