
#define AREF 1127


void setup(){
  Serial.begin(57600);
  // Set the default voltage of the reference voltage
  analogReference(INTERNAL);
}

void loop(){

    float accum[5] = {0};
    for(int i =0; i < 32; i++){
        for(int j =0; j < 5 ; j++){;
          accum[j] +=  analogRead(j);
          
          delayMicroseconds(2000);
        }
    }

  for(int j=0;j<5;++j){
    float sensor_value = accum[j]/32;
    float voltage = sensor_value * (AREF/1024.0);
    float voltage_diference=voltage-400.0;
    float concentration=voltage_diference*50.0/16.0;
    Serial.print(concentration);
    Serial.print(",");
    }
  Serial.println("");

}
