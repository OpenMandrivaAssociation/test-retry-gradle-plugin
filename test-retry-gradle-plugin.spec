Name:		test-retry-gradle-plugin
Version:	1.6.5
Release:	1
Summary:	Gradle plugin that retries failed tests
Group:		Development/Java
License:	Apache-2.0
URL:		https://github.com/gradle/test-retry-gradle-plugin
# Tag v1.6.5. Gradle and Maven wrapper jars are not in this archive.
Source0:	test-retry-gradle-plugin-%{version}.tar.gz

BuildArch:	noarch
BuildRequires:	java-21-openjdk-devel
BuildRequires:	kotlin
BuildRequires:	kotlin-libs
BuildRequires:	gradle
BuildRequires:	sysjar
BuildRequires:	javapackages-filesystem
BuildRequires:	jakarta-inject
BuildRequires:	mvn(org.ow2.asm:asm)

%description
Gradle plugin id org.gradle.test-retry. It adds a retry extension to
each Test task. The sources are compiled with javac and kotlinc.
The Gradle tool is not invoked. ASM stays the system library instead
of the shaded copy upstream embeds. kotlinc 2.0.21 needs JDK 21.

%prep
%autosetup -n test-retry-gradle-plugin-%{version} -p1
find . -type f \( -name '*.jar' -o -name '*.class' -o -name '*.so' -o -name '*.node' -o -name '*.wasm' \) -print > binaries.list
find . -type d -name '*.jar' -print >> binaries.list
if [ -s binaries.list ]; then
	cat binaries.list
	exit 1
fi

%build
set -eo pipefail
export JAVA_HOME=%{_jvmdir}/java-21-openjdk
export PATH="$JAVA_HOME/bin:$PATH"
find plugin/src/main/java -name '*.java' | sort > sources.list
find plugin/src/main/kotlin -name '*.kt' | sort > kotlin.list
test "$(wc -l < sources.list)" -eq 28
test "$(wc -l < kotlin.list)" -eq 1
CP=%{_javadir}/asm.jar
CP="$CP:$(find %{_datadir}/gradle -name '*.jar' | sort | paste -sd: -)"
CP="$CP:%{_javadir}/atinject.jar"
test -s %{_javadir}/asm.jar
test -s %{_javadir}/atinject.jar
mkdir -p classes
javac -encoding UTF-8 --release 8 -Xlint:-options -proc:none -cp "$CP" -d classes @sources.list
kotlinc -jvm-target 1.8 -language-version 1.8 -api-version 1.8 -cp "$CP:classes" -d classes $(cat kotlin.list)
mkdir -p classes/META-INF/gradle-plugins
printf '%s\n' 'implementation-class=org.gradle.testretry.TestRetryPlugin' > classes/META-INF/gradle-plugins/org.gradle.test-retry.properties
printf '%s\n' 'Automatic-Module-Name: org.gradle.testretry' > manifest.mf
jar cfm test-retry-gradle-plugin.jar manifest.mf -C classes .
jar i test-retry-gradle-plugin.jar
javap -v -classpath test-retry-gradle-plugin.jar org.gradle.testretry.TestRetryPlugin | grep -F -q 'major version: 52'
javap -v -classpath test-retry-gradle-plugin.jar org.gradle.kotlin.dsl.TestRetryKt | grep -F -q 'major version: 52'
jar tf test-retry-gradle-plugin.jar | grep -F -q 'META-INF/gradle-plugins/org.gradle.test-retry.properties'
desc=$(jar --describe-module --file test-retry-gradle-plugin.jar)
printf '%s\n' "$desc" | grep -F -q 'org.gradle.testretry'
if printf '%s\n' "$desc" | grep -F -q 'Unable'; then
	exit 1
fi

cat > test-retry-gradle-plugin.pom << END
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>org.gradle</groupId>
  <artifactId>test-retry-gradle-plugin</artifactId>
  <version>%{version}</version>
  <name>Gradle test retry plugin</name>
  <description>Mitigate flaky tests by retrying tests when they fail</description>
  <url>https://github.com/gradle/test-retry-gradle-plugin</url>
  <licenses>
    <license>
      <name>Apache-2.0</name>
      <url>https://www.apache.org/licenses/LICENSE-2.0</url>
    </license>
  </licenses>
  <dependencies>
    <dependency>
      <groupId>org.ow2.asm</groupId>
      <artifactId>asm</artifactId>
      <version>9.11.1</version>
    </dependency>
  </dependencies>
</project>
END

%install
sysjar install --buildroot %{buildroot} \
	--artifact test-retry-gradle-plugin.pom:test-retry-gradle-plugin.jar \
	--file-name test-retry-gradle-plugin \
	--filelist .mfiles

%check
set -eo pipefail
export JAVA_HOME=%{_jvmdir}/java-21-openjdk
export PATH="$JAVA_HOME/bin:$PATH"
JAR=%{buildroot}%{_javadir}/test-retry-gradle-plugin.jar
test -s "$JAR"
CP=%{_javadir}/asm.jar
CP="$CP:$(find %{_datadir}/gradle -name '*.jar' | sort | paste -sd: -)"
CP="$CP:%{_javadir}/atinject.jar"
mkdir -p check
cat > check/Smoke.java << 'EOF'
import org.gradle.api.Project;
import org.gradle.api.tasks.testing.Test;
import org.gradle.testfixtures.ProjectBuilder;
import org.gradle.testretry.TestRetryPlugin;
import org.gradle.testretry.TestRetryTaskExtension;

public class Smoke {
	public static void main(String[] args) {
		int code = 1;
		try {
			Project project = ProjectBuilder.builder().build();
			project.getPlugins().apply("java");
			project.getPlugins().apply(TestRetryPlugin.class);
			Test test = (Test) project.getTasks().getByName("test");
			TestRetryTaskExtension ext = (TestRetryTaskExtension) test.getExtensions().getByName(TestRetryTaskExtension.NAME);
			ext.getMaxRetries().set(2);
			ext.getMaxFailures().set(4);
			int retries = ext.getMaxRetries().get();
			int failures = ext.getMaxFailures().get();
			if (retries != 2 || failures != 4) {
				throw new AssertionError(retries + " " + failures);
			}
			System.out.println(args[0] + " " + TestRetryTaskExtension.NAME + " " + retries + " " + failures);
			code = 0;
		} catch (Throwable t) {
			t.printStackTrace();
		}
		Runtime.getRuntime().halt(code);
	}
}
EOF
javac -encoding UTF-8 --release 8 -Xlint:-options -proc:none -cp "$JAR:$CP" -d check check/Smoke.java
java \
	--add-opens=java.base/java.lang=ALL-UNNAMED \
	--add-opens=java.base/java.lang.invoke=ALL-UNNAMED \
	--add-opens=java.base/java.util=ALL-UNNAMED \
	--add-opens=java.prefs/java.util.prefs=ALL-UNNAMED \
	--add-exports=jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED \
	--add-exports=jdk.compiler/com.sun.tools.javac.util=ALL-UNNAMED \
	--add-opens=java.base/java.nio.charset=ALL-UNNAMED \
	--add-opens=java.base/java.net=ALL-UNNAMED \
	--add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED \
	--add-opens=java.xml/javax.xml.namespace=ALL-UNNAMED \
	-cp "check:$JAR:$CP" Smoke retry_ok > check/out.txt
cat check/out.txt
grep -F -q 'retry_ok retry 2 4' check/out.txt

%files -f .mfiles
%doc README.adoc
%license LICENSE
