
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
    float voltage = sensor_value * (1127/1024.0);
    float voltage_diference=voltage-400.0;
    float concentration=voltage_diference*50.0/16.0;
    Serial.print(concentration);
    Serial.print(",");
//     delay(100);
    }
  Serial.println("");
// 
//  // The analog signal is converted to a voltage
//  float voltage = sensorValue*(5000/1024.0);
//  if(voltage == 0)
//  {
//    Serial.println("Fault");
//  }
//  else if(voltage < 400)
//  {
//    Serial.println("preheating");
//  }
//  else
//  {
//    int voltage_diference=voltage-400;
//    float concentration=voltage_diference*50.0/16.0;
//    // Print Voltage
//    Serial.print("voltage:");
//    Serial.print(voltage);
//    Serial.println("mv");
//    //Print CO2 concentration
//    Serial.print(concentration);
//    Serial.println("ppm");
//  }
}
